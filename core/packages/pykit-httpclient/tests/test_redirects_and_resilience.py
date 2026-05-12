"""Tests for redirect handling and resilience integration."""

from __future__ import annotations

from collections import deque

import httpx
import pytest

from pykit_httpclient import AuthConfig, HttpClient, HttpConfig
from pykit_httpclient.errors import ErrorCode, HttpError
from pykit_resilience import PolicyConfig, RetryConfig


def _transport(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_cross_origin_redirect_strips_authorization() -> None:
    seen_auth: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_auth.append(request.headers.get("authorization"))
        if request.url.host == "origin.example.com":
            return httpx.Response(302, headers={"location": "https://other.example.com/final"})
        return httpx.Response(200, json={"ok": True})

    client = HttpClient(
        HttpConfig(
            base_url="https://origin.example.com",
            auth=AuthConfig(type="bearer", token="secret-token"),
            follow_redirects=True,
            max_redirects=3,
        ),
        transport=_transport(handler),
    )

    response = await client.get("/start")
    await client.close()

    assert response.status_code == 200
    assert seen_auth == ["Bearer secret-token", None]


@pytest.mark.asyncio
async def test_resilience_retry_retries_retryable_http_errors() -> None:
    attempts: deque[int] = deque([1, 2, 3])

    def handler(request: httpx.Request) -> httpx.Response:
        attempt = attempts.popleft()
        if attempt < 3:
            return httpx.Response(503, text="retry")
        return httpx.Response(200, json={"attempt": attempt})

    client = HttpClient(
        HttpConfig(
            base_url="https://api.example.com",
            resilience=PolicyConfig(retry=RetryConfig(max_attempts=3, initial_backoff=0.0, jitter=0.0)),
        ),
        transport=_transport(handler),
    )

    response = await client.get("/retry")
    await client.close()

    assert response.json() == {"attempt": 3}
    assert not attempts


@pytest.mark.asyncio
async def test_too_many_redirects_are_validation_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://api.example.com/loop"})

    client = HttpClient(
        HttpConfig(
            base_url="https://api.example.com",
            follow_redirects=True,
            max_redirects=1,
        ),
        transport=_transport(handler),
    )

    with pytest.raises(HttpError) as exc_info:
        await client.get("/start")
    await client.close()

    assert exc_info.value.code == ErrorCode.VALIDATION
    assert exc_info.value.retryable is False
