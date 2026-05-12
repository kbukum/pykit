"""ASGI-compatible health check registry."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

Scope = dict[str, Any]
Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]


class HealthRegistry:
    """ASGI-compatible health check registry for /healthz and /readyz endpoints.

    Usage::

        registry = HealthRegistry()
        registry.register("database", db_health_check)

        # Mount as ASGI app:
        app.add_route("/healthz", registry)
    """

    def __init__(self) -> None:
        self._liveness_checks: dict[str, Callable[[], Awaitable[Any]]] = {}
        self._readiness_checks: dict[str, Callable[[], Awaitable[Any]]] = {}

    def register_liveness(self, name: str, check: Callable[[], Awaitable[Any]]) -> None:
        """Register a liveness check (is the process alive?)."""
        self._liveness_checks[name] = check

    def register_readiness(self, name: str, check: Callable[[], Awaitable[Any]]) -> None:
        """Register a readiness check (is the service ready to serve traffic?)."""
        self._readiness_checks[name] = check

    def register(self, name: str, check: Callable[[], Awaitable[Any]]) -> None:
        """Register both a liveness and readiness check under the same name."""
        self.register_liveness(name, check)
        self.register_readiness(name, check)

    async def _run_checks(
        self, checks: dict[str, Callable[[], Awaitable[Any]]]
    ) -> tuple[dict[str, Any], bool]:
        results: dict[str, Any] = {}
        healthy = True
        for name, check in checks.items():
            try:
                detail = await check()
                results[name] = {"status": "ok", "detail": detail}
            except Exception as e:
                results[name] = {"status": "error", "detail": str(e)}
                healthy = False
        return results, healthy

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return

        path = scope.get("path", "")
        if path in ("/healthz", "/health"):
            checks = self._liveness_checks
        elif path in ("/readyz", "/ready"):
            checks = self._readiness_checks
        else:
            await send(
                {
                    "type": "http.response.start",
                    "status": 404,
                    "headers": [[b"content-type", b"application/json"]],
                }
            )
            await send({"type": "http.response.body", "body": b'{"detail":"Not Found"}'})
            return

        results, healthy = await self._run_checks(checks)
        body = json.dumps({"status": "ok" if healthy else "error", "checks": results}).encode()
        status = 200 if healthy else 503

        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [[b"content-type", b"application/json"]],
            }
        )
        await send({"type": "http.response.body", "body": body})
