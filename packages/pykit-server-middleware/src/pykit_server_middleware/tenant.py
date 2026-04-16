"""Multi-tenant ASGI middleware using contextvars.

Mirrors gokit's server/middleware/tenant.go and rskit-http's tenant_middleware.
Uses the same contextvar name as pykit-server's gRPC TenantInterceptor so both
transports share a single tenant context when running in the same process.
"""

from __future__ import annotations

import contextvars
from collections.abc import Awaitable, Callable, MutableMapping
from dataclasses import dataclass, field
from typing import Any

Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

_tenant_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("tenant_id", default=None)


def set_tenant(tenant_id: str) -> contextvars.Token[str | None]:
    """Set the current tenant ID in the context.

    Args:
        tenant_id: The tenant/workspace identifier.

    Returns:
        A token that can be used to reset the context variable.
    """
    return _tenant_var.set(tenant_id)


def get_tenant() -> str | None:
    """Get the current tenant ID from the context.

    Returns:
        The tenant ID, or None if not set.
    """
    return _tenant_var.get()


def require_tenant() -> str:
    """Get the current tenant ID, raising if not set.

    Returns:
        The tenant ID.

    Raises:
        RuntimeError: If no tenant is set in the current context.
    """
    tenant_id = _tenant_var.get()
    if tenant_id is None:
        msg = "No tenant ID set in current context"
        raise RuntimeError(msg)
    return tenant_id


@dataclass(frozen=True)
class TenantConfig:
    """Configuration for tenant middleware.

    Attributes:
        header_name: HTTP header to extract tenant ID from.
        required: If True, requests without tenant header get 403.
        skip_paths: Paths to skip tenant extraction (e.g., health checks).
    """

    header_name: str = "X-Tenant-ID"
    required: bool = True
    skip_paths: frozenset[str] = field(default_factory=frozenset)


class TenantMiddleware:
    """ASGI middleware that extracts tenant ID from request headers.

    Sets the tenant ID in a contextvar so downstream handlers can
    access it via get_tenant() / require_tenant().

    Mirrors gokit's server/middleware Tenant() and rskit-http's tenant_middleware.
    """

    def __init__(self, app: ASGIApp, config: TenantConfig | None = None) -> None:
        self._app = app
        self._config = config or TenantConfig()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self._app(scope, receive, send)
            return

        path = scope.get("path", "")
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

        if tenant_id is not None:
            token = set_tenant(tenant_id)
            try:
                await self._app(scope, receive, send)
            finally:
                _tenant_var.reset(token)
        else:
            await self._app(scope, receive, send)


async def _send_forbidden(send: Send) -> None:
    """Send a 403 response for missing tenant."""
    await send(
        {
            "type": "http.response.start",
            "status": 403,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": b'{"error":"missing tenant ID"}',
        }
    )
