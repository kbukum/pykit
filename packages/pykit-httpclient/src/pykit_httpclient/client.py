"""Async HTTP client built on httpx."""

from __future__ import annotations

import base64
from typing import Any

import httpx

from pykit_httpclient.config import AuthConfig, HttpConfig
from pykit_httpclient.errors import classify_status, connection_error, timeout_error
from pykit_httpclient.types import Request, Response


class HttpClient:
    """Async HTTP client with auth, header merging, and error classification."""

    def __init__(self, config: HttpConfig, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._config = config
        kwargs: dict[str, Any] = {
            "base_url": config.base_url,
            "timeout": config.timeout,
            "follow_redirects": config.follow_redirects,
            "headers": dict(config.headers),
        }
        if transport is not None:
            kwargs["transport"] = transport
        self._client = httpx.AsyncClient(**kwargs)

    @property
    def config(self) -> HttpConfig:
        return self._config

    async def request(self, req: Request) -> Response:
        """Execute a full HTTP request with auth, header merging, and error classification."""
        headers = dict(req.headers)
        auth = req.auth or self._config.auth
        if auth is not None:
            _apply_auth(auth, headers)

        # Encode body
        content: bytes | None = None
        json_body: Any = None
        if req.body is not None:
            if isinstance(req.body, bytes):
                content = req.body
            elif isinstance(req.body, str):
                content = req.body.encode()
                headers.setdefault("content-type", "text/plain")
            else:
                json_body = req.body

        try:
            resp = await self._client.request(
                method=req.method,
                url=req.path,
                headers=headers,
                params=req.query or None,
                content=content,
                json=json_body,
            )
        except httpx.TimeoutException as exc:
            raise timeout_error(str(exc)) from exc
        except httpx.ConnectError as exc:
            raise connection_error(str(exc)) from exc

        result = Response(
            status_code=resp.status_code,
            headers=dict(resp.headers),
            body=resp.content,
        )

        err = classify_status(resp.status_code, resp.content)
        if err is not None:
            raise err

        return result

    # ---- Convenience methods ----

    async def get(self, path: str, **kwargs: Any) -> Response:
        return await self.request(Request(method="GET", path=path, **kwargs))

    async def post(self, path: str, body: Any = None, **kwargs: Any) -> Response:
        return await self.request(Request(method="POST", path=path, body=body, **kwargs))

    async def put(self, path: str, body: Any = None, **kwargs: Any) -> Response:
        return await self.request(Request(method="PUT", path=path, body=body, **kwargs))

    async def patch(self, path: str, body: Any = None, **kwargs: Any) -> Response:
        return await self.request(Request(method="PATCH", path=path, body=body, **kwargs))

    async def delete(self, path: str, **kwargs: Any) -> Response:
        return await self.request(Request(method="DELETE", path=path, **kwargs))

    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()


def _apply_auth(auth: AuthConfig, headers: dict[str, str]) -> None:
    """Apply authentication to request headers."""
    match auth.type:
        case "bearer":
            headers["authorization"] = f"Bearer {auth.token}"
        case "basic":
            cred = base64.b64encode(f"{auth.username}:{auth.password}".encode()).decode()
            headers["authorization"] = f"Basic {cred}"
        case "api_key":
            headers[auth.header_name.lower()] = auth.token
