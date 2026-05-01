"""HTTP/ASGI middleware folded into pykit-server."""

from __future__ import annotations

import asyncio
import contextlib
import json
import math
import threading
import time
from collections.abc import Awaitable, Callable, MutableMapping
from dataclasses import dataclass, field
from typing import Any, cast

from opentelemetry import trace
from opentelemetry.propagate import extract, inject
from opentelemetry.trace import StatusCode
from prometheus_client import Counter, Histogram, generate_latest

from pykit_observability import get_tracer
from pykit_resilience import RateLimiter as ResilienceRateLimiter
from pykit_resilience import RateLimiterConfig as ResilienceRateLimiterConfig
from pykit_server.tenant import _tenant_context, get_tenant, require_tenant, set_tenant

Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

_tenant_var = _tenant_context


def ip_based_key(scope: Scope) -> str:
    """Extract a rate limit key from the client IP."""
    for name, value in scope.get("headers", []):
        if name == b"x-forwarded-for":
            return cast("str", value.decode("latin-1").split(",")[0].strip())
    client = scope.get("client")
    if client:
        return cast("str", client[0])
    return "unknown"


def user_based_key(scope: Scope) -> str:
    """Extract a rate limit key from authenticated user state."""
    state = scope.get("state", {})
    uid = state.get("user_id")
    if isinstance(uid, str) and uid:
        return uid
    return ip_based_key(scope)


@dataclass(frozen=True)
class TenantConfig:
    """Configuration for HTTP tenant extraction."""

    header_name: str = "X-Tenant-ID"
    required: bool = True
    skip_paths: frozenset[str] = field(default_factory=frozenset)


class TenantMiddleware:
    """ASGI middleware that extracts tenant ID from request headers."""

    def __init__(self, app: ASGIApp, config: TenantConfig | None = None) -> None:
        self._app = app
        self._config = config or TenantConfig()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self._app(scope, receive, send)
            return

        path = cast("str", scope.get("path", ""))
        if path in self._config.skip_paths:
            await self._app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        header_key = self._config.header_name.lower().encode("latin-1")
        raw = headers.get(header_key, b"")
        tenant_id = raw.decode("latin-1") if raw else None

        if tenant_id is None and self._config.required:
            await _send_forbidden(send)
            return

        if tenant_id is None:
            await self._app(scope, receive, send)
            return

        token = set_tenant(tenant_id)
        try:
            await self._app(scope, receive, send)
        finally:
            _tenant_var.reset(token)


class _ASGIHeaderCarrier:
    """Adapt ASGI headers to the OpenTelemetry text map interface."""

    def __init__(self, scope: MutableMapping[str, Any]) -> None:
        self._scope = scope

    def _headers(self) -> list[tuple[bytes, bytes]]:
        return cast("list[tuple[bytes, bytes]]", self._scope.get("headers", []))

    def get(self, key: str, default: str | None = None) -> str | None:
        key_lower = key.lower().encode("latin-1")
        for header_key, value in self._headers():
            if header_key == key_lower:
                return value.decode("latin-1")
        return default

    def set(self, key: str, value: str) -> None:
        headers = [(k, v) for k, v in self._headers() if k != key.lower().encode("latin-1")]
        headers.append((key.lower().encode("latin-1"), value.encode("latin-1")))
        self._scope["headers"] = headers

    def keys(self) -> list[str]:
        return [key.decode("latin-1") for key, _ in self._headers()]


class _ResponseHeaderCarrier:
    """Collect headers for OpenTelemetry injection into responses."""

    def __init__(self) -> None:
        self.headers: list[tuple[bytes, bytes]] = []

    def get(self, key: str, default: str | None = None) -> str | None:
        key_lower = key.lower().encode("latin-1")
        for header_key, value in self.headers:
            if header_key == key_lower:
                return value.decode("latin-1")
        return default

    def set(self, key: str, value: str) -> None:
        self.headers.append((key.lower().encode("latin-1"), value.encode("latin-1")))

    def __setitem__(self, key: str, value: str) -> None:
        self.set(key, value)

    def __getitem__(self, key: str) -> str | None:
        return self.get(key)

    def keys(self) -> list[str]:
        return [key.decode("latin-1") for key, _ in self.headers]


class TracingMiddleware:
    """ASGI middleware that creates OpenTelemetry spans per HTTP request."""

    def __init__(self, app: ASGIApp, *, service_name: str = "http.server") -> None:
        self._app = app
        self._service_name = service_name

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        method = cast("str", scope.get("method", "GET"))
        path = cast("str", scope.get("path", "/"))
        scheme = cast("str", scope.get("scheme", "http"))

        ctx = extract(carrier=_ASGIHeaderCarrier(scope))
        tracer = get_tracer(self._service_name)

        with tracer.start_as_current_span(
            f"{method} {path}",
            context=ctx,
            kind=trace.SpanKind.SERVER,
            attributes={
                "http.method": method,
                "http.target": path,
                "http.scheme": scheme,
            },
        ) as span:
            response_carrier = _ResponseHeaderCarrier()
            inject(carrier=response_carrier)
            status_code = 200

            async def send_wrapper(message: MutableMapping[str, Any]) -> None:
                nonlocal status_code
                if message["type"] == "http.response.start":
                    status_code = int(message.get("status", 200))
                    existing = list(message.get("headers", []))
                    existing.extend(response_carrier.headers)
                    message["headers"] = existing
                await send(message)

            try:
                await self._app(scope, receive, send_wrapper)
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(StatusCode.ERROR, str(exc))
                raise
            finally:
                span.set_attribute("http.status_code", status_code)
                if status_code >= 500:
                    span.set_status(StatusCode.ERROR, f"HTTP {status_code}")


_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "path", "status_code"],
)
_request_duration = Histogram(
    "http_request_duration_seconds",
    "Duration of HTTP requests in seconds",
    ["method", "path", "status_code"],
)
_request_size = Histogram(
    "http_request_size_bytes",
    "Size of HTTP request bodies in bytes",
    ["method", "path"],
)
_response_size = Histogram(
    "http_response_size_bytes",
    "Size of HTTP response bodies in bytes",
    ["method", "path"],
)


class PrometheusMiddleware:
    """ASGI middleware that records HTTP metrics with Prometheus."""

    def __init__(
        self, app: ASGIApp, *, service_name: str = "http.server", metrics_path: str = "/metrics"
    ) -> None:
        del service_name
        self._app = app
        self._metrics_path = metrics_path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        path = cast("str", scope.get("path", "/"))
        if path == self._metrics_path:
            await self._serve_metrics(send)
            return

        method = cast("str", scope.get("method", "GET"))
        start = time.monotonic()
        request_size = 0
        for key, value in scope.get("headers", []):
            if key == b"content-length":
                with contextlib.suppress(ValueError):
                    request_size = int(value)
                break
        if request_size > 0:
            _request_size.labels(method=method, path=path).observe(request_size)

        status_code = 200
        response_bytes = 0

        async def send_wrapper(message: MutableMapping[str, Any]) -> None:
            nonlocal status_code, response_bytes
            if message["type"] == "http.response.start":
                status_code = int(message.get("status", 200))
            elif message["type"] == "http.response.body":
                response_bytes += len(cast("bytes", message.get("body", b"")))
            await send(message)

        try:
            await self._app(scope, receive, send_wrapper)
        finally:
            duration = time.monotonic() - start
            labels = {"method": method, "path": path, "status_code": str(status_code)}
            _requests_total.labels(**labels).inc()
            _request_duration.labels(**labels).observe(duration)
            _response_size.labels(method=method, path=path).observe(response_bytes)

    async def _serve_metrics(self, send: Send) -> None:
        body = generate_latest()
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"content-length", str(len(body)).encode("latin-1")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


@dataclass
class RateLimitConfig:
    """Configuration for HTTP rate limiting."""

    requests_per_minute: int = 60
    key_func: Callable[[Scope], str] | None = None
    limit_func: Callable[[Scope], tuple[str, int]] | None = None
    cleanup_interval: float = 300.0
    bucket_ttl: float = 600.0


@dataclass(slots=True)
class _Bucket:
    """Bucket entry guarded by :attr:`RateLimiter._lock`."""

    limiter: ResilienceRateLimiter
    requests_per_minute: int
    last_access: float


class RateLimiter:
    """Per-key rate limiter registry backed by pykit-resilience."""

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

        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()
        self._stop_event = asyncio.Event()
        self._cleanup_task: asyncio.Task[None] | None = None
        self._now_func: Callable[[], float] = time.time

    def _build_limiter(self, key: str, rpm: int) -> ResilienceRateLimiter:
        safe_rpm = max(rpm, 1)
        return ResilienceRateLimiter(
            ResilienceRateLimiterConfig(
                name=f"http:{key}",
                rate=safe_rpm / 60.0,
                burst=safe_rpm,
            )
        )

    def start(self) -> None:
        """Start the stale bucket cleanup task.

        This method must be called from within a running asyncio event loop.
        """
        if self._cleanup_task is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError as exc:
                raise RuntimeError(
                    "RateLimiter.start() must be called from within a running asyncio event loop"
                ) from exc
            self._stop_event = asyncio.Event()
            self._cleanup_task = loop.create_task(self._cleanup())

    def stop(self) -> None:
        """Stop the stale bucket cleanup task."""
        self._stop_event.set()
        cleanup_task = self._cleanup_task
        if cleanup_task is None:
            return
        if cleanup_task.done():
            try:
                cleanup_task.result()
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            return

        def _cleanup_finished(task: asyncio.Task[None]) -> None:
            try:
                task.result()
            except asyncio.CancelledError:
                pass
            finally:
                if self._cleanup_task is task:
                    self._cleanup_task = None

        cleanup_task.add_done_callback(_cleanup_finished)
        cleanup_task.cancel()

    def _get_or_create_bucket_locked(self, key: str, rpm: int, now: float) -> _Bucket:
        bucket = self._buckets.get(key)
        if bucket is None or bucket.requests_per_minute != rpm:
            bucket = _Bucket(
                limiter=self._build_limiter(key, rpm),
                requests_per_minute=rpm,
                last_access=now,
            )
            self._buckets[key] = bucket
        return bucket

    def _evict_stale_buckets_locked(self, now: float) -> None:
        stale_before = now - self.cfg.bucket_ttl
        stale_keys = [key for key, bucket in self._buckets.items() if bucket.last_access < stale_before]
        for key in stale_keys:
            del self._buckets[key]

    def _evict_stale_buckets(self, now: float) -> None:
        with self._lock:
            self._evict_stale_buckets_locked(now)

    def allow(self, key: str, rpm: int) -> tuple[bool, int, int, float, int]:
        """Check whether a request is allowed.

        Returns (allowed, limit, remaining, retry_after_secs, reset_unix).
        """
        safe_rpm = max(rpm, 1)
        with self._lock:
            bucket = self._get_or_create_bucket_locked(key, safe_rpm, self._now_func())
            decision = bucket.limiter.take()
            accessed_at = self._now_func()
            bucket.last_access = accessed_at

        reset_unix = int(accessed_at + decision.reset_after)
        return decision.allowed, decision.limit, decision.remaining, decision.retry_after, reset_unix

    async def _cleanup(self) -> None:
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(self.cfg.cleanup_interval)
            except asyncio.CancelledError:
                return

            self._evict_stale_buckets(self._now_func())


class RateLimitMiddleware:
    """ASGI middleware that applies per-key rate limiting via pykit-resilience."""

    def __init__(self, app: ASGIApp, limiter: RateLimiter) -> None:
        self._app = app
        self._limiter = limiter

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

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
        headers = [
            (b"x-ratelimit-limit", str(limit).encode("latin-1")),
            (b"x-ratelimit-remaining", str(remaining).encode("latin-1")),
            (b"x-ratelimit-reset", str(reset_unix).encode("latin-1")),
        ]

        if not allowed:
            retry_header = str(math.ceil(retry_after)).encode("latin-1")
            await send(
                {
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [
                        *headers,
                        (b"retry-after", retry_header),
                        (b"content-type", b"application/json"),
                    ],
                }
            )
            await send(
                {"type": "http.response.body", "body": json.dumps({"error": "rate limit exceeded"}).encode()}
            )
            return

        async def send_wrapper(message: MutableMapping[str, Any]) -> None:
            if message["type"] == "http.response.start":
                existing = list(message.get("headers", []))
                existing.extend(headers)
                message["headers"] = existing
            await send(message)

        await self._app(scope, receive, send_wrapper)


async def _send_forbidden(send: Send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 403,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": b'{"error":"missing tenant ID"}'})


__all__ = [
    "PrometheusMiddleware",
    "RateLimitConfig",
    "RateLimitMiddleware",
    "RateLimiter",
    "TenantConfig",
    "TenantMiddleware",
    "TracingMiddleware",
    "get_tenant",
    "ip_based_key",
    "require_tenant",
    "set_tenant",
    "user_based_key",
]
