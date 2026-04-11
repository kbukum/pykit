"""ASGI middleware for API key validation."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any, Protocol, runtime_checkable

from pykit_auth_apikey.apikey import Key

Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


@runtime_checkable
class KeyValidator(Protocol):
    """Validates an API key and returns its metadata."""

    async def validate_key(self, plain_key: str) -> Key: ...


class APIKeyMiddleware:
    """ASGI middleware that validates API keys from a configurable header.

    If the header is absent, the request passes through (allowing other auth).
    If present but invalid, returns 401.
    """

    def __init__(
        self,
        app: ASGIApp,
        validator: KeyValidator,
        *,
        header_name: str = "x-api-key",
    ) -> None:
        self.app = app
        self.validator = validator
        self.header_name = header_name.lower().encode("latin-1")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        raw_key = headers.get(self.header_name)

        if raw_key is None:
            await self.app(scope, receive, send)
            return

        try:
            key = await self.validator.validate_key(raw_key.decode("latin-1"))
        except Exception:
            body = json.dumps({"error": "invalid or expired API key"}).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        [b"content-type", b"application/json"],
                        [b"content-length", str(len(body)).encode()],
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        scope.setdefault("state", {})["apikey"] = key
        scope.setdefault("state", {})["apikey_owner_id"] = key.owner_id
        await self.app(scope, receive, send)
