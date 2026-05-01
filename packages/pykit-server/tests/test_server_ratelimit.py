"""Tests for HTTP rate limiting middleware."""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import Awaitable, Callable, Iterator, MutableMapping
from typing import Any, cast

import pytest

from pykit_server.middleware import (
    RateLimitConfig,
    RateLimiter,
    RateLimitMiddleware,
    ip_based_key,
    user_based_key,
)

ASGIMessage = MutableMapping[str, Any]
Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[ASGIMessage]]
Send = Callable[[ASGIMessage], Awaitable[None]]


def _make_scope(
    method: str = "GET",
    path: str = "/api/test",
    client: tuple[str, int] = ("127.0.0.1", 8000),
    headers: list[tuple[bytes, bytes]] | None = None,
    state: dict[str, Any] | None = None,
) -> Scope:
    scope: Scope = {
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


async def _simple_app(scope: Scope, receive: Receive, send: Send) -> None:
    """Minimal ASGI app that returns 200."""
    del scope, receive
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain")],
        }
    )
    await send({"type": "http.response.body", "body": b"OK"})


async def _receive() -> ASGIMessage:
    return {"type": "http.request", "body": b""}


def _collector(messages: list[ASGIMessage]) -> Send:
    async def _send(message: ASGIMessage) -> None:
        messages.append(message)

    return _send


async def _noop_send(message: ASGIMessage) -> None:
    _ = message


def _status(message: ASGIMessage) -> int:
    return cast("int", message["status"])


def _headers(message: ASGIMessage) -> dict[bytes, bytes]:
    return dict(cast("list[tuple[bytes, bytes]]", message["headers"]))


@pytest.fixture()
def limiter() -> Iterator[RateLimiter]:
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
        sent: list[ASGIMessage] = []
        await app(_make_scope(), _receive, _collector(sent))
        assert _status(sent[0]) == 200

    async def test_response_headers_set(self, limiter: RateLimiter) -> None:
        app = RateLimitMiddleware(_simple_app, limiter)
        sent: list[ASGIMessage] = []
        await app(_make_scope(), _receive, _collector(sent))

        headers = _headers(sent[0])
        assert b"x-ratelimit-limit" in headers
        assert b"x-ratelimit-remaining" in headers
        assert b"x-ratelimit-reset" in headers
        assert headers[b"x-ratelimit-limit"] == b"5"

    async def test_429_after_exceeding_limit(self, limiter: RateLimiter) -> None:
        app = RateLimitMiddleware(_simple_app, limiter)

        for _ in range(5):
            sent: list[ASGIMessage] = []
            await app(_make_scope(), _receive, _collector(sent))
            assert _status(sent[0]) == 200

        sent = []
        await app(_make_scope(), _receive, _collector(sent))
        assert _status(sent[0]) == 429

        headers = _headers(sent[0])
        assert b"retry-after" in headers
        assert int(headers[b"retry-after"]) > 0

        body = json.loads(cast("bytes", sent[1]["body"]))
        assert body == {"error": "rate limit exceeded"}

    async def test_non_http_passes_through(self, limiter: RateLimiter) -> None:
        called = False

        async def ws_app(scope: Scope, receive: Receive, send: Send) -> None:
            del scope, receive, send
            nonlocal called
            called = True

        app = RateLimitMiddleware(ws_app, limiter)
        await app({"type": "websocket"}, _receive, _noop_send)
        assert called

    async def test_custom_key_func(self) -> None:
        cfg = RateLimitConfig(
            requests_per_minute=2,
            key_func=lambda scope: cast("str", scope.get("path", "/")),
        )
        rl = RateLimiter(cfg)
        try:
            app = RateLimitMiddleware(_simple_app, rl)

            for _ in range(2):
                sent: list[ASGIMessage] = []
                await app(_make_scope(path="/path-a"), _receive, _collector(sent))
                assert _status(sent[0]) == 200

            sent = []
            await app(_make_scope(path="/path-a"), _receive, _collector(sent))
            assert _status(sent[0]) == 429

            sent = []
            await app(_make_scope(path="/path-b"), _receive, _collector(sent))
            assert _status(sent[0]) == 200
        finally:
            rl.stop()

    async def test_limit_func_tiered(self) -> None:
        def tiered_limit(scope: Scope) -> tuple[str, int]:
            state = cast("dict[str, Any]", scope.get("state", {}))
            if state.get("tier") == "premium":
                return "premium-user", 100
            return ip_based_key(scope), 2

        cfg = RateLimitConfig(limit_func=tiered_limit)
        rl = RateLimiter(cfg)
        try:
            app = RateLimitMiddleware(_simple_app, rl)

            for _ in range(2):
                sent: list[ASGIMessage] = []
                await app(
                    _make_scope(client=("10.0.0.1", 8000)),
                    _receive,
                    _collector(sent),
                )
                assert _status(sent[0]) == 200

            sent = []
            await app(
                _make_scope(client=("10.0.0.1", 8000)),
                _receive,
                _collector(sent),
            )
            assert _status(sent[0]) == 429

            for _ in range(5):
                sent = []
                await app(
                    _make_scope(state={"tier": "premium"}),
                    _receive,
                    _collector(sent),
                )
                assert _status(sent[0]) == 200
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
            rl.allow("stale-key", 10)
            assert "stale-key" in rl._buckets

            rl._now_func = lambda: time.time() + 1.0

            rl.start()
            await asyncio.sleep(0.3)

            assert "stale-key" not in rl._buckets
        finally:
            rl._now_func = time.time
            rl.stop()

    def test_cleanup_waits_for_inflight_decision(self) -> None:
        class _Decision:
            allowed = True
            limit = 1
            remaining = 0
            retry_after = 0.0
            reset_after = 60.0

        class _BlockingLimiter:
            def __init__(self) -> None:
                self.started = threading.Event()
                self.release = threading.Event()

            def take(self) -> _Decision:
                self.started.set()
                released = self.release.wait(timeout=1.0)
                assert released
                return _Decision()

        rl = RateLimiter(
            RateLimitConfig(
                requests_per_minute=1,
                cleanup_interval=0.1,
                bucket_ttl=1.0,
            )
        )
        blocking_limiter = _BlockingLimiter()
        cast("Any", rl)._build_limiter = lambda key, rpm: blocking_limiter
        current_time = 0.0
        rl._now_func = lambda: current_time

        result: list[tuple[bool, int, int, float, int]] = []

        def _allow() -> None:
            result.append(rl.allow("shared-key", 1))

        def _cleanup() -> None:
            rl._evict_stale_buckets(current_time)

        worker = threading.Thread(target=_allow)
        worker.start()
        assert blocking_limiter.started.wait(timeout=1.0)

        current_time = 10.0
        cleanup = threading.Thread(target=_cleanup)
        cleanup.start()
        cleanup.join(timeout=0.1)
        assert cleanup.is_alive()

        blocking_limiter.release.set()
        worker.join(timeout=1.0)
        cleanup.join(timeout=1.0)

        assert not cleanup.is_alive()
        assert result == [(True, 1, 0, 0.0, 70)]
        assert "shared-key" in rl._buckets
        assert rl._buckets["shared-key"].last_access == pytest.approx(10.0)

    def test_start_requires_running_event_loop(self) -> None:
        rl = RateLimiter(RateLimitConfig(requests_per_minute=1))
        with pytest.raises(RuntimeError, match="running asyncio event loop"):
            rl.start()
