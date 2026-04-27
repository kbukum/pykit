"""OpenTelemetry tracing middleware for ASGI applications."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any, cast

from opentelemetry import trace
from opentelemetry.propagate import extract, inject
from opentelemetry.trace import StatusCode


class _ASGIHeaderCarrier:
    """Adapts ASGI scope headers to the OpenTelemetry TextMap interface."""

    def __init__(self, scope: MutableMapping[str, Any]) -> None:
        self._scope = scope

    def _headers(self) -> list[tuple[bytes, bytes]]:
        return cast("list[tuple[bytes, bytes]]", self._scope.get("headers", []))

    def get(self, key: str, default: str | None = None) -> str | None:
        key_lower = key.lower().encode("latin-1")
        for k, v in self._headers():
            if k == key_lower:
                return v.decode("latin-1")
        return default

    def set(self, key: str, value: str) -> None:
        headers = list(self._headers())
        key_bytes = key.lower().encode("latin-1")
        value_bytes = value.encode("latin-1")
        headers = [(k, v) for k, v in headers if k != key_bytes]
        headers.append((key_bytes, value_bytes))
        self._scope["headers"] = headers

    def keys(self) -> list[str]:
        return [k.decode("latin-1") for k, _ in self._headers()]


class _ResponseHeaderCarrier:
    """Collects headers for injection into ASGI response start message."""

    def __init__(self) -> None:
        self.headers: list[tuple[bytes, bytes]] = []

    def get(self, key: str, default: str | None = None) -> str | None:
        key_lower = key.lower().encode("latin-1")
        for k, v in self.headers:
            if k == key_lower:
                return v.decode("latin-1")
        return default

    def set(self, key: str, value: str) -> None:
        self.headers.append((key.lower().encode("latin-1"), value.encode("latin-1")))

    def __setitem__(self, key: str, value: str) -> None:
        self.set(key, value)

    def __getitem__(self, key: str) -> str | None:
        return self.get(key)

    def keys(self) -> list[str]:
        return [k.decode("latin-1") for k, _ in self.headers]


Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


class TracingMiddleware:
    """ASGI middleware that creates OpenTelemetry spans per HTTP request.

    Sets attributes: http.method, http.target, http.scheme, http.status_code.
    Extracts W3C TraceContext from incoming headers and injects trace context
    into response headers.
    """

    def __init__(self, app: ASGIApp, *, service_name: str = "http.server") -> None:
        self._app = app
        self._service_name = service_name

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        path = scope.get("path", "/")
        scheme = scope.get("scheme", "http")

        ctx = extract(carrier=_ASGIHeaderCarrier(scope))
        span_name = f"{method} {path}"
        tracer = trace.get_tracer(self._service_name)

        with tracer.start_as_current_span(
            span_name,
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
                    status_code = message.get("status", 200)
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
