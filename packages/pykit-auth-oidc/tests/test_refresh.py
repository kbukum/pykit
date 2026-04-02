"""Tests for OAuth2/OIDC token refresh."""

from __future__ import annotations

import json
from urllib.parse import urlencode

import httpx
import pytest

from pykit_auth_oidc.refresh import RefreshError, refresh_token
from pykit_auth_oidc.types import RefreshConfig, TokenResult


def _mock_transport(handler):
    return httpx.MockTransport(handler)


def _json_token_response(
    access_token: str = "new-access",
    refresh_token: str = "new-refresh",
    expires_in: int = 3600,
    token_type: str = "Bearer",
    scope: str = "openid profile",
) -> dict:
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": expires_in,
        "token_type": token_type,
        "scope": scope,
    }


class TestRefreshToken:
    async def test_json_response(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["content-type"] == "application/x-www-form-urlencoded"
            body = request.content.decode()
            assert "grant_type=refresh_token" in body
            assert "client_id=my-client" in body
            assert "refresh_token=old-refresh" in body
            return httpx.Response(200, json=_json_token_response())

        config = RefreshConfig(
            token_endpoint="https://auth.example.com/token",
            client_id="my-client",
            client_secret="secret",
            refresh_token="old-refresh",
        )

        async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
            result = await refresh_token(config, client=client)

        assert result.access_token == "new-access"
        assert result.refresh_token == "new-refresh"
        assert result.token_type == "Bearer"
        assert result.expires_at is not None
        assert result.scopes == ["openid", "profile"]

    async def test_form_encoded_response(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = urlencode({
                "access_token": "form-access",
                "token_type": "bearer",
                "expires_in": "7200",
            })
            return httpx.Response(200, content=body.encode())

        config = RefreshConfig(
            token_endpoint="https://auth.example.com/token",
            client_id="my-client",
            refresh_token="old-refresh",
        )

        async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
            result = await refresh_token(config, client=client)

        assert result.access_token == "form-access"
        assert result.token_type == "bearer"
        assert result.expires_at is not None

    async def test_missing_endpoint_raises(self) -> None:
        config = RefreshConfig(
            token_endpoint="",
            client_id="my-client",
            refresh_token="token",
        )
        with pytest.raises(RefreshError, match="token endpoint is required"):
            await refresh_token(config)

    async def test_missing_refresh_token_raises(self) -> None:
        config = RefreshConfig(
            token_endpoint="https://auth.example.com/token",
            client_id="my-client",
            refresh_token="",
        )
        with pytest.raises(RefreshError, match="refresh token is required"):
            await refresh_token(config)

    async def test_http_error_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "invalid_grant"})

        config = RefreshConfig(
            token_endpoint="https://auth.example.com/token",
            client_id="my-client",
            refresh_token="bad-token",
        )

        async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
            with pytest.raises(RefreshError) as exc_info:
                await refresh_token(config, client=client)
            assert exc_info.value.status_code == 401

    async def test_scopes_sent_in_request(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = request.content.decode()
            assert "scope=openid+email" in body or "scope=openid email" in body
            return httpx.Response(200, json=_json_token_response())

        config = RefreshConfig(
            token_endpoint="https://auth.example.com/token",
            client_id="my-client",
            refresh_token="tok",
            scopes=["openid", "email"],
        )

        async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
            result = await refresh_token(config, client=client)
        assert result.access_token == "new-access"

    async def test_extra_params_sent(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = request.content.decode()
            assert "audience=my-api" in body
            return httpx.Response(200, json=_json_token_response())

        config = RefreshConfig(
            token_endpoint="https://auth.example.com/token",
            client_id="my-client",
            refresh_token="tok",
            extra_params={"audience": "my-api"},
        )

        async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
            result = await refresh_token(config, client=client)
        assert result.access_token == "new-access"

    async def test_default_token_type(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            resp = _json_token_response()
            resp.pop("token_type")
            return httpx.Response(200, json=resp)

        config = RefreshConfig(
            token_endpoint="https://auth.example.com/token",
            client_id="my-client",
            refresh_token="tok",
        )

        async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
            result = await refresh_token(config, client=client)
        assert result.token_type == "Bearer"
