"""Extended tests for OAuth2/OIDC token refresh — edge cases and security."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from urllib.parse import urlencode

import httpx
import pytest

from pykit_auth_oidc.refresh import RefreshError, refresh_token
from pykit_auth_oidc.types import RefreshConfig


def _mock_transport(handler):
    return httpx.MockTransport(handler)


def _base_config(**overrides) -> RefreshConfig:
    defaults = {
        "token_endpoint": "https://auth.example.com/token",
        "client_id": "my-client",
        "refresh_token": "old-refresh",
    }
    defaults.update(overrides)
    return RefreshConfig(**defaults)


# ---------------------------------------------------------------------------
# Network / HTTP edge cases
# ---------------------------------------------------------------------------


class TestRefreshNetworkErrors:
    async def test_network_error_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        config = _base_config()
        async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
            with pytest.raises(RefreshError, match="sending refresh request"):
                await refresh_token(config, client=client)

    async def test_http_500_raises_with_status(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"error": "server_error"})

        config = _base_config()
        async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
            with pytest.raises(RefreshError) as exc_info:
                await refresh_token(config, client=client)
            assert exc_info.value.status_code == 500

    async def test_http_403_raises_with_status(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, text="Forbidden")

        config = _base_config()
        async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
            with pytest.raises(RefreshError) as exc_info:
                await refresh_token(config, client=client)
            assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Malformed response handling
# ---------------------------------------------------------------------------


class TestRefreshMalformedResponses:
    async def test_empty_body_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"")

        config = _base_config()
        async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
            with pytest.raises(RefreshError):
                await refresh_token(config, client=client)

    async def test_json_without_access_token_falls_through(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"token_type": "Bearer"})

        config = _base_config()
        async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
            with pytest.raises(RefreshError):
                await refresh_token(config, client=client)

    async def test_invalid_json_with_no_form_fallback(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"not-json-not-form\x00\x01\x02")

        config = _base_config()
        async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
            with pytest.raises(RefreshError):
                await refresh_token(config, client=client)


# ---------------------------------------------------------------------------
# Response field edge cases
# ---------------------------------------------------------------------------


class TestRefreshFieldEdgeCases:
    async def test_expires_in_zero(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "access_token": "tok",
                    "expires_in": 0,
                },
            )

        config = _base_config()
        async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
            result = await refresh_token(config, client=client)
        assert result.access_token == "tok"
        assert result.expires_at is None  # 0 → no expiry set

    async def test_expires_in_negative(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "access_token": "tok",
                    "expires_in": -100,
                },
            )

        config = _base_config()
        async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
            result = await refresh_token(config, client=client)
        assert result.access_token == "tok"
        assert result.expires_at is None  # negative → no expiry set

    async def test_id_token_preserved(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "access_token": "at",
                    "id_token": "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.sig",
                    "refresh_token": "rt",
                },
            )

        config = _base_config()
        async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
            result = await refresh_token(config, client=client)
        assert result.id_token.startswith("eyJ")

    async def test_empty_scope_yields_empty_list(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "access_token": "tok",
                    "scope": "",
                },
            )

        config = _base_config()
        async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
            result = await refresh_token(config, client=client)
        assert result.scopes == []

    async def test_expires_at_in_future(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "access_token": "tok",
                    "expires_in": 7200,
                },
            )

        before = datetime.now(UTC)
        config = _base_config()
        async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
            result = await refresh_token(config, client=client)
        assert result.expires_at is not None
        assert result.expires_at > before


# ---------------------------------------------------------------------------
# Client secret & public client
# ---------------------------------------------------------------------------


class TestRefreshClientSecret:
    async def test_no_client_secret_for_public_client(self) -> None:
        captured_body: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_body.append(request.content.decode())
            return httpx.Response(
                200,
                json={"access_token": "tok"},
            )

        config = _base_config(client_secret="")
        async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
            await refresh_token(config, client=client)
        assert "client_secret" not in captured_body[0]

    async def test_client_secret_included_when_set(self) -> None:
        captured_body: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_body.append(request.content.decode())
            return httpx.Response(
                200,
                json={"access_token": "tok"},
            )

        config = _base_config(client_secret="my-secret")
        async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
            await refresh_token(config, client=client)
        assert "client_secret=my-secret" in captured_body[0]


# ---------------------------------------------------------------------------
# Form-encoded response edge cases
# ---------------------------------------------------------------------------


class TestRefreshFormEncoded:
    async def test_form_encoded_with_non_numeric_expires_in(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = urlencode(
                {
                    "access_token": "form-tok",
                    "expires_in": "not-a-number",
                }
            )
            return httpx.Response(200, content=body.encode())

        config = _base_config()
        async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
            result = await refresh_token(config, client=client)
        assert result.access_token == "form-tok"
        assert result.expires_at is None  # non-numeric → defaults to 0 → no expiry
