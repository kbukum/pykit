"""Prometheus metrics middleware for ASGI applications."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from prometheus_client import Counter, Histogram, generate_latest

Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


class PrometheusMiddleware:
    """ASGI middleware that records HTTP metrics with Prometheus.

    Metrics:

    - ``http_requests_total``  — counter with labels method, path, status_code
    - ``http_request_duration_seconds`` — histogram
    - ``http_request_size_bytes`` — histogram (from content-length)
    - ``http_response_size_bytes`` — histogram (sum of response body chunks)

    Exposes a ``/metrics`` endpoint that returns Prometheus text format.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        service_name: str = "http.server",
        metrics_path: str = "/metrics",
    ) -> None:
        self._app = app
        self._metrics_path = metrics_path
        self._requests_total = Counter(
            "http_requests_total",
            "Total number of HTTP requests",
            ["method", "path", "status_code"],
        )
        self._request_duration = Histogram(
            "http_request_duration_seconds",
            "Duration of HTTP requests in seconds",
            ["method", "path", "status_code"],
        )
        self._request_size = Histogram(
            "http_request_size_bytes",
            "Size of HTTP request bodies in bytes",
            ["method", "path"],
        )
        self._response_size = Histogram(
            "http_response_size_bytes",
            "Size of HTTP response bodies in bytes",
            ["method", "path"],
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        path = scope.get("path", "/")

        if path == self._metrics_path:
            await self._serve_metrics(scope, receive, send)
            return

        method = scope.get("method", "GET")
        start = time.monotonic()

        # Read request content-length from headers
        request_size = 0
        for k, v in scope.get("headers", []):
            if k == b"content-length":
                try:
                    request_size = int(v)
                except ValueError:
                    pass
                break

        if request_size > 0:
            self._request_size.labels(method=method, path=path).observe(request_size)

        status_code = 200
        response_bytes = 0

        async def send_wrapper(message: MutableMapping[str, Any]) -> None:
            nonlocal status_code, response_bytes
            if message["type"] == "http.response.start":
                status_code = message.get("status", 200)
            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                response_bytes += len(body)
            await send(message)

        try:
            await self._app(scope, receive, send_wrapper)
        finally:
            duration = time.monotonic() - start
            labels = {"method": method, "path": path, "status_code": str(status_code)}
            self._requests_total.labels(**labels).inc()
            self._request_duration.labels(**labels).observe(duration)
            self._response_size.labels(method=method, path=path).observe(response_bytes)

    async def _serve_metrics(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Serve the /metrics endpoint with Prometheus text output."""
        body = generate_latest()
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"content-type", b"text/plain; charset=utf-8"),
                (b"content-length", str(len(body)).encode()),
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })
