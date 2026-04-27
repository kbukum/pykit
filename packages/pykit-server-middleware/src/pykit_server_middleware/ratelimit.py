"""HTTP rate limiting ASGI middleware using token-bucket algorithm."""

from __future__ import annotations

import asyncio
import json
import math
import threading
import time
from collections.abc import Awaitable, Callable, MutableMapping
from dataclasses import dataclass
from typing import Any, cast

Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


def ip_based_key(scope: Scope) -> str:
    """Extract client IP from ASGI scope headers (X-Forwarded-For, then scope client)."""
    for name, value in scope.get("headers", []):
        if name == b"x-forwarded-for":
            return cast("str", value.decode("latin-1").split(",")[0].strip())
    client = scope.get("client")
    if client:
        return cast("str", client[0])
    return "unknown"


def user_based_key(scope: Scope) -> str:
    """Extract user_id from scope state, falling back to IP."""
    state = scope.get("state", {})
    uid = state.get("user_id")
    if isinstance(uid, str) and uid:
        return uid
    return ip_based_key(scope)


@dataclass
class RateLimitConfig:
    """Configuration for the rate limiting middleware."""

    requests_per_minute: int = 60
    key_func: Callable[[Scope], str] | None = None
    limit_func: Callable[[Scope], tuple[str, int]] | None = None
    cleanup_interval: float = 300.0
    bucket_ttl: float = 600.0


class _TokenBucket:
    """Classic token-bucket rate limiter (thread-safe)."""

    __slots__ = ("_mu", "last_access", "last_refill", "max_tokens", "refill_rate", "tokens")

    def __init__(self, rpm: int, now: float) -> None:
        self._mu = threading.Lock()
        self.max_tokens = float(rpm)
        self.refill_rate = rpm / 60.0
        self.tokens = self.max_tokens
        self.last_refill = now
        self.last_access = now

    def allow(self, now: float) -> tuple[bool, int, float]:
        """Consume one token. Returns (allowed, remaining, retry_after_seconds)."""
        with self._mu:
            elapsed = now - self.last_refill
            self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now
            self.last_access = now

            if self.tokens >= 1:
                self.tokens -= 1
                return True, int(self.tokens), 0.0

            retry_after = (1 - self.tokens) / self.refill_rate
            return False, 0, retry_after

    def is_stale(self, now: float, ttl: float) -> bool:
        with self._mu:
            return (now - self.last_access) > ttl


class RateLimiter:
    """Manages per-key token buckets with background cleanup."""

    def __init__(self, cfg: RateLimitConfig | None = None) -> None:
        self.cfg = cfg or RateLimitConfig()
        if self.cfg.requests_per_minute <= 0:
            self.cfg.requests_per_minute = 60
        if self.cfg.limit_func is None and self.cfg.key_func is None:
            self.cfg.key_func = ip_based_key
        if self.cfg.cleanup_interval <= 0:
            self.cfg.cleanup_interval = 300.0
        if self.cfg.bucket_ttl <= 0:
            self.cfg.bucket_ttl = 600.0

        self._buckets: dict[str, _TokenBucket] = {}
        self._lock = threading.Lock()
        self._stop_event = asyncio.Event()
        self._cleanup_task: asyncio.Task[None] | None = None
        self._now_func: Callable[[], float] = time.time

    def start(self) -> None:
        """Start the background cleanup task. Call from an async context."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.ensure_future(self._cleanup())

    async def stop(self) -> None:
        """Cancel and await the background cleanup task."""
        self._stop_event.set()
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            finally:
                self._cleanup_task = None

    def allow(self, key: str, rpm: int) -> tuple[bool, int, int, float, int]:
        """Check whether a request is allowed.

        Returns (allowed, limit, remaining, retry_after_secs, reset_unix).
        """
        now = self._now_func()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _TokenBucket(rpm, now)
                self._buckets[key] = bucket

        allowed, remaining, retry_after = bucket.allow(now)

        tokens_to_refill = rpm - remaining
        refill_rate = rpm / 60.0
        reset_secs = tokens_to_refill / refill_rate if refill_rate > 0 else 0
        reset_unix = int(now + reset_secs)

        return allowed, rpm, remaining, retry_after, reset_unix

    async def _cleanup(self) -> None:
        """Periodically evict stale buckets."""
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(self.cfg.cleanup_interval)
            except asyncio.CancelledError:
                return
            now = self._now_func()
            with self._lock:
                stale_keys = [k for k, b in self._buckets.items() if b.is_stale(now, self.cfg.bucket_ttl)]
                for k in stale_keys:
                    del self._buckets[k]


class RateLimitMiddleware:
    """ASGI middleware that applies per-key token-bucket rate limiting.

    Sets standard rate limit response headers and returns 429 when the
    limit is exceeded.
    """

    def __init__(self, app: ASGIApp, limiter: RateLimiter) -> None:
        self._app = app
        self._limiter = limiter

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        # Lazily start background cleanup on first request.
        if self._limiter._cleanup_task is None:
            self._limiter.start()

        cfg = self._limiter.cfg
        if cfg.limit_func is not None:
            key, rpm = cfg.limit_func(scope)
        else:
            key_fn = cfg.key_func or ip_based_key
            key = key_fn(scope)
            rpm = cfg.requests_per_minute

        allowed, limit, remaining, retry_after, reset_unix = self._limiter.allow(key, rpm)

        rl_headers = [
            (b"x-ratelimit-limit", str(limit).encode("latin-1")),
            (b"x-ratelimit-remaining", str(remaining).encode("latin-1")),
            (b"x-ratelimit-reset", str(reset_unix).encode("latin-1")),
        ]

        if not allowed:
            retry_hdr = str(math.ceil(retry_after)).encode("latin-1")
            headers = [*rl_headers, (b"retry-after", retry_hdr), (b"content-type", b"application/json")]
            body = json.dumps({"error": "rate limit exceeded"}).encode("utf-8")
            await send(
                {
                    "type": "http.response.start",
                    "status": 429,
                    "headers": headers,
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        async def send_wrapper(message: MutableMapping[str, Any]) -> None:
            if message["type"] == "http.response.start":
                existing = list(message.get("headers", []))
                existing.extend(rl_headers)
                message["headers"] = existing
            await send(message)

        await self._app(scope, receive, send_wrapper)
