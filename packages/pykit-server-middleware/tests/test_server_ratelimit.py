"""Tests for HTTP rate limiting middleware."""

from __future__ import annotations

import asyncio
import json
import time

import pytest

from pykit_server_middleware.ratelimit import (
    RateLimitConfig,
    RateLimitMiddleware,
    RateLimiter,
    ip_based_key,
    user_based_key,
)


def _make_scope(
    method: str = "GET",
    path: str = "/api/test",
    client: tuple[str, int] = ("127.0.0.1", 8000),
    headers: list[tuple[bytes, bytes]] | None = None,
    state: dict | None = None,
) -> dict:
    scope: dict = {
        "type": "http",
        "method": method,
        "path": path,
        "scheme": "http",
        "headers": headers or [],
        "client": client,
    }
    if state is not None:
        scope["state"] = state
    return scope


async def _simple_app(scope, receive, send):
    """Minimal ASGI app that returns 200."""
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain")],
        }
    )
    await send({"type": "http.response.body", "body": b"OK"})


async def _receive():
    return {"type": "http.request", "body": b""}


async def _collect(lst, msg):
    lst.append(msg)


async def _noop():
    pass


@pytest.fixture()
def limiter():
    rl = RateLimiter(RateLimitConfig(requests_per_minute=5))
    yield rl
    rl.stop()


class TestTokenBucket:
    def test_allows_within_limit(self, limiter: RateLimiter) -> None:
        for _ in range(5):
            allowed, *_ = limiter.allow("key1", 5)
            assert allowed

    def test_blocks_after_limit(self, limiter: RateLimiter) -> None:
        for _ in range(5):
            limiter.allow("key1", 5)
        allowed, _, remaining, retry_after, _ = limiter.allow("key1", 5)
        assert not allowed
        assert remaining == 0
        assert retry_after > 0


class TestRateLimitMiddleware:
    async def test_requests_within_limit_pass(self, limiter: RateLimiter) -> None:
        app = RateLimitMiddleware(_simple_app, limiter)
        sent: list[dict] = []
        await app(_make_scope(), _receive, lambda m: _collect(sent, m))
        assert sent[0]["status"] == 200

    async def test_response_headers_set(self, limiter: RateLimiter) -> None:
        app = RateLimitMiddleware(_simple_app, limiter)
        sent: list[dict] = []
        await app(_make_scope(), _receive, lambda m: _collect(sent, m))

        headers = dict(sent[0]["headers"])
        assert b"x-ratelimit-limit" in headers
        assert b"x-ratelimit-remaining" in headers
        assert b"x-ratelimit-reset" in headers
        assert headers[b"x-ratelimit-limit"] == b"5"

    async def test_429_after_exceeding_limit(self, limiter: RateLimiter) -> None:
        app = RateLimitMiddleware(_simple_app, limiter)

        for _ in range(5):
            sent: list[dict] = []
            await app(_make_scope(), _receive, lambda m: _collect(sent, m))
            assert sent[0]["status"] == 200

        sent = []
        await app(_make_scope(), _receive, lambda m: _collect(sent, m))
        assert sent[0]["status"] == 429

        headers = dict(sent[0]["headers"])
        assert b"retry-after" in headers
        assert int(headers[b"retry-after"]) > 0

        body = json.loads(sent[1]["body"])
        assert body == {"error": "rate limit exceeded"}

    async def test_non_http_passes_through(self, limiter: RateLimiter) -> None:
        called = False

        async def ws_app(scope, receive, send):
            nonlocal called
            called = True

        app = RateLimitMiddleware(ws_app, limiter)
        await app({"type": "websocket"}, _receive, lambda m: _noop())
        assert called

    async def test_custom_key_func(self) -> None:
        cfg = RateLimitConfig(
            requests_per_minute=2,
            key_func=lambda scope: scope.get("path", "/"),
        )
        rl = RateLimiter(cfg)
        try:
            app = RateLimitMiddleware(_simple_app, rl)

            # Exhaust limit for /path-a
            for _ in range(2):
                sent: list[dict] = []
                await app(_make_scope(path="/path-a"), _receive, lambda m: _collect(sent, m))
                assert sent[0]["status"] == 200

            # /path-a now blocked
            sent = []
            await app(_make_scope(path="/path-a"), _receive, lambda m: _collect(sent, m))
            assert sent[0]["status"] == 429

            # /path-b still allowed
            sent = []
            await app(_make_scope(path="/path-b"), _receive, lambda m: _collect(sent, m))
            assert sent[0]["status"] == 200
        finally:
            rl.stop()

    async def test_limit_func_tiered(self) -> None:
        def tiered_limit(scope):
            state = scope.get("state", {})
            if state.get("tier") == "premium":
                return "premium-user", 100
            return ip_based_key(scope), 2

        cfg = RateLimitConfig(limit_func=tiered_limit)
        rl = RateLimiter(cfg)
        try:
            app = RateLimitMiddleware(_simple_app, rl)

            # Regular user limited at 2 RPM
            for _ in range(2):
                sent: list[dict] = []
                await app(
                    _make_scope(client=("10.0.0.1", 8000)),
                    _receive,
                    lambda m: _collect(sent, m),
                )
                assert sent[0]["status"] == 200

            sent = []
            await app(
                _make_scope(client=("10.0.0.1", 8000)),
                _receive,
                lambda m: _collect(sent, m),
            )
            assert sent[0]["status"] == 429

            # Premium user has higher limit
            for _ in range(5):
                sent = []
                await app(
                    _make_scope(state={"tier": "premium"}),
                    _receive,
                    lambda m: _collect(sent, m),
                )
                assert sent[0]["status"] == 200
        finally:
            rl.stop()


class TestKeyExtractors:
    def test_ip_based_key_from_client(self) -> None:
        scope = _make_scope(client=("192.168.1.1", 9000))
        assert ip_based_key(scope) == "192.168.1.1"

    def test_ip_based_key_from_forwarded(self) -> None:
        scope = _make_scope(headers=[(b"x-forwarded-for", b"10.0.0.1, 10.0.0.2")])
        assert ip_based_key(scope) == "10.0.0.1"

    def test_user_based_key_with_user(self) -> None:
        scope = _make_scope(state={"user_id": "alice"})
        assert user_based_key(scope) == "alice"

    def test_user_based_key_falls_back_to_ip(self) -> None:
        scope = _make_scope(client=("10.0.0.5", 8000))
        assert user_based_key(scope) == "10.0.0.5"


class TestCleanup:
    async def test_stale_buckets_evicted(self) -> None:
        cfg = RateLimitConfig(
            requests_per_minute=10,
            cleanup_interval=0.1,
            bucket_ttl=0.2,
        )
        rl = RateLimiter(cfg)
        try:
            # Access a bucket
            rl.allow("stale-key", 10)
            assert "stale-key" in rl._buckets

            # Override time to make bucket stale
            original_now = rl._now_func
            rl._now_func = lambda: time.time() + 1.0

            # Start cleanup and wait for it to run
            rl.start()
            await asyncio.sleep(0.3)

            assert "stale-key" not in rl._buckets
        finally:
            rl._now_func = time.time
            rl.stop()
