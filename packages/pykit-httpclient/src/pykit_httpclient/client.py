"""Async HTTP client built on httpx."""

from __future__ import annotations

import base64
from dataclasses import replace
from typing import Any

import httpx

from pykit_httpclient.config import AuthConfig, HttpConfig
from pykit_httpclient.errors import (
    ErrorCode,
    HttpError,
    classify_status,
    connection_error,
    is_retryable,
    timeout_error,
)
from pykit_httpclient.types import Request, Response
from pykit_resilience import Policy, PolicyConfig

_SENSITIVE_HEADERS = frozenset({"authorization", "proxy-authorization", "cookie"})


class HttpClient:
    """Async HTTP client with auth, redirects, resilience, and error classification."""

    def __init__(self, config: HttpConfig, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._config = config
        self._policy = _build_policy(config.resilience)
        kwargs: dict[str, Any] = {
            "base_url": config.base_url,
            "timeout": config.timeout,
            "follow_redirects": False,
            "headers": dict(config.headers),
        }
        if transport is not None:
            kwargs["transport"] = transport
        self._client = httpx.AsyncClient(**kwargs)

    @property
    def config(self) -> HttpConfig:
        return self._config

    async def request(self, req: Request) -> Response:
        """Execute a full HTTP request with auth, redirects, resilience, and error classification."""
        headers = dict(req.headers)
        auth = req.auth or self._config.auth
        sensitive_headers = set(_SENSITIVE_HEADERS)
        if auth is not None:
            sensitive_headers.update(_apply_auth(auth, headers))

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

        async def execute() -> Response:
            try:
                resp = await self._send_with_redirects(
                    method=req.method,
                    path=req.path,
                    headers=headers,
                    params=req.query or None,
                    content=content,
                    json=json_body,
                    sensitive_headers=sensitive_headers,
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

        if self._policy is not None:
            return await self._policy.execute(execute)
        return await execute()

    async def _send_with_redirects(
        self,
        *,
        method: str,
        path: str,
        headers: dict[str, str],
        params: dict[str, str] | None,
        content: bytes | None,
        json: Any,
        sensitive_headers: set[str],
    ) -> httpx.Response:
        request = self._client.build_request(
            method=method,
            url=path,
            headers=headers,
            params=params,
            content=content,
            json=json,
        )
        response = await self._client.send(request, follow_redirects=False)
        redirects_followed = 0

        while self._config.follow_redirects and response.is_redirect:
            next_request = response.next_request
            if next_request is None:
                return response
            redirects_followed += 1
            if redirects_followed > self._config.max_redirects:
                raise HttpError("too many redirects", code=ErrorCode.VALIDATION, retryable=False)
            if _origin_tuple(request.url) != _origin_tuple(next_request.url):
                for header_name in sensitive_headers:
                    next_request.headers.pop(header_name, None)
            request = next_request
            response = await self._client.send(request, follow_redirects=False)

        return response

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


def _build_policy(config: PolicyConfig | None) -> Policy | None:
    if config is None:
        return None
    retry_config = config.retry
    if retry_config is not None and retry_config.retry_if is None:
        retry_config = replace(retry_config, retry_if=is_retryable)
        config = replace(config, retry=retry_config)
    return Policy(config)


def _origin_tuple(url: httpx.URL) -> tuple[str, str, int | None]:
    return (url.scheme, url.host or "", url.port)


def _apply_auth(auth: AuthConfig, headers: dict[str, str]) -> set[str]:
    """Apply authentication to request headers and return sensitive header names."""
    match auth.type:
        case "bearer":
            headers["authorization"] = f"Bearer {auth.token}"
            return {"authorization"}
        case "basic":
            cred = base64.b64encode(f"{auth.username}:{auth.password}".encode()).decode()
            headers["authorization"] = f"Basic {cred}"
            return {"authorization"}
        case "api_key":
            header_name = auth.header_name.lower()
            headers[header_name] = auth.token
            return {header_name}
    return set()
