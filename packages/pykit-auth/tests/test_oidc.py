"""Tests for bundled OIDC support."""

from __future__ import annotations

import json

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from pykit_auth import (
    JWKSCache,
    OIDCClientConfig,
    OIDCClientType,
    OIDCError,
    OIDCIDTokenValidator,
    RefreshConfig,
    build_authorization_request,
    generate_code_verifier,
    parse_discovery_document,
    refresh_token,
    validate_callback,
)


def _discovery() -> dict[str, object]:
    return {
        "issuer": "https://issuer.example.com",
        "authorization_endpoint": "https://issuer.example.com/authorize",
        "token_endpoint": "https://issuer.example.com/token",
        "jwks_uri": "https://issuer.example.com/jwks",
        "response_types_supported": ["code"],
        "code_challenge_methods_supported": ["S256"],
        "id_token_signing_alg_values_supported": ["RS256"],
    }


def _rsa_keypair() -> tuple[object, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    return private_key, private_pem


def _jwk(public_key: object, kid: str) -> dict[str, object]:
    payload = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(public_key))
    payload["kid"] = kid
    payload["alg"] = "RS256"
    payload["use"] = "sig"
    return payload


class FakeAsyncClient:
    def __init__(self, response: httpx.Response) -> None:
        self._response = response

    async def __aenter__(self) -> FakeAsyncClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    async def get(self, url: str) -> httpx.Response:
        return self._response

    async def post(self, url: str, data: dict[str, str], headers: dict[str, str]) -> httpx.Response:
        return self._response

    async def aclose(self) -> None:
        return None


def test_discovery_and_pkce_validation() -> None:
    discovery = parse_discovery_document(_discovery())
    config = OIDCClientConfig(
        issuer="https://issuer.example.com",
        client_id="client-1",
        redirect_uri="https://client.example.com/callback",
    )

    with pytest.raises(OIDCError, match="PKCE"):
        build_authorization_request(discovery, config, code_verifier=None)

    request = build_authorization_request(discovery, config, code_verifier=generate_code_verifier())
    assert "code_challenge_method=S256" in request.url
    assert request.state
    assert request.nonce


def test_discovery_and_client_validation_errors() -> None:
    with pytest.raises(OIDCError, match="invalid OIDC discovery document"):
        parse_discovery_document(b"not-json")

    with pytest.raises(OIDCError, match="invalid OIDC discovery document"):
        parse_discovery_document("[]")

    invalid_alg_discovery = dict(_discovery())
    invalid_alg_discovery["id_token_signing_alg_values_supported"] = ["HS256"]
    with pytest.raises(OIDCError, match="invalid OIDC discovery document"):
        parse_discovery_document(invalid_alg_discovery)

    mixed_alg_discovery = dict(_discovery())
    mixed_alg_discovery["id_token_signing_alg_values_supported"] = ["PS256", "RS256"]
    assert parse_discovery_document(mixed_alg_discovery).id_token_signing_alg_values_supported == (
        "PS256",
        "RS256",
    )

    with pytest.raises(ValueError, match="client_secret"):
        OIDCClientConfig(
            issuer="https://issuer.example.com",
            client_id="client-1",
            redirect_uri="https://client.example.com/callback",
            client_type=OIDCClientType.CONFIDENTIAL,
        )

    with pytest.raises(ValueError, match="redirect_uri"):
        OIDCClientConfig(
            issuer="https://issuer.example.com",
            client_id="client-1",
            redirect_uri="http://evil.example.com/callback",
        )

    with pytest.raises(ValueError, match="between 0 and 60"):
        OIDCClientConfig(
            issuer="https://issuer.example.com",
            client_id="client-1",
            redirect_uri="https://client.example.com/callback",
            leeway_seconds=61,
        )

    with pytest.raises(ValueError, match="between 43 and 128"):
        generate_code_verifier(10)

    discovery = parse_discovery_document(_discovery())
    config = OIDCClientConfig(
        issuer="https://issuer.example.com",
        client_id="client-1",
        redirect_uri="https://client.example.com/callback",
    )
    with pytest.raises(OIDCError, match="openid scope"):
        build_authorization_request(
            discovery, config, code_verifier=generate_code_verifier(), scopes=("profile",)
        )

    confidential = OIDCClientConfig(
        issuer="https://issuer.example.com",
        client_id="client-1",
        redirect_uri="https://client.example.com/callback",
        client_type=OIDCClientType.CONFIDENTIAL,
        client_secret="secret",
    )
    request = build_authorization_request(discovery, confidential, code_verifier=None)
    assert request.code_verifier


def test_callback_rejects_state_and_nonce_mismatch() -> None:
    with pytest.raises(OIDCError, match="state mismatch"):
        validate_callback(
            expected_state="expected",
            received_state="wrong",
            expected_nonce="nonce",
            id_token_claims={"nonce": "nonce"},
        )

    with pytest.raises(OIDCError, match="nonce mismatch"):
        validate_callback(
            expected_state="expected",
            received_state="expected",
            expected_nonce="nonce",
            id_token_claims={"nonce": "wrong"},
        )


@pytest.mark.asyncio
async def test_refresh_requires_rotation(monkeypatch: pytest.MonkeyPatch) -> None:
    response = httpx.Response(
        200,
        json={"access_token": "new-access", "refresh_token": "new-refresh"},
        request=httpx.Request("POST", "https://issuer.example.com/token"),
    )
    monkeypatch.setattr("pykit_auth.oidc.httpx.AsyncClient", lambda timeout: FakeAsyncClient(response))

    result = await refresh_token(
        RefreshConfig(
            token_endpoint="https://issuer.example.com/token",
            client_id="client-1",
            refresh_token="old-refresh",
        )
    )
    assert result.refresh_token == "new-refresh"

    stale_response = httpx.Response(
        200,
        json={"access_token": "new-access", "refresh_token": "old-refresh"},
        request=httpx.Request("POST", "https://issuer.example.com/token"),
    )
    monkeypatch.setattr("pykit_auth.oidc.httpx.AsyncClient", lambda timeout: FakeAsyncClient(stale_response))
    with pytest.raises(OIDCError, match="rotation"):
        await refresh_token(
            RefreshConfig(
                token_endpoint="https://issuer.example.com/token",
                client_id="client-1",
                refresh_token="old-refresh",
            )
        )


@pytest.mark.asyncio
async def test_refresh_error_and_form_response_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    error_response = httpx.Response(
        500,
        request=httpx.Request("POST", "https://issuer.example.com/token"),
        json={"error": "server_error"},
    )
    monkeypatch.setattr("pykit_auth.oidc.httpx.AsyncClient", lambda timeout: FakeAsyncClient(error_response))
    with pytest.raises(OIDCError, match="refresh request failed"):
        await refresh_token(
            RefreshConfig(
                token_endpoint="https://issuer.example.com/token",
                client_id="client-1",
                refresh_token="old-refresh",
            )
        )

    form_response = httpx.Response(
        200,
        content=b"access_token=form%2Baccess&refresh_token=form-refresh&expires_in=3600&scope=openid+email",
        request=httpx.Request("POST", "https://issuer.example.com/token"),
    )
    monkeypatch.setattr("pykit_auth.oidc.httpx.AsyncClient", lambda timeout: FakeAsyncClient(form_response))
    result = await refresh_token(
        RefreshConfig(
            token_endpoint="https://issuer.example.com/token",
            client_id="client-1",
            refresh_token="old-refresh",
        )
    )
    assert result.access_token == "form+access"
    assert result.scopes == ("openid", "email")

    invalid_response = httpx.Response(
        200,
        content=b"not-a-token-response",
        request=httpx.Request("POST", "https://issuer.example.com/token"),
    )
    monkeypatch.setattr(
        "pykit_auth.oidc.httpx.AsyncClient", lambda timeout: FakeAsyncClient(invalid_response)
    )
    with pytest.raises(OIDCError, match="invalid token response"):
        await refresh_token(
            RefreshConfig(
                token_endpoint="https://issuer.example.com/token",
                client_id="client-1",
                refresh_token="old-refresh",
                require_refresh_rotation=False,
            )
        )

    malformed_jwks_response = httpx.Response(
        200,
        content=b"{not-json",
        request=httpx.Request("GET", "https://issuer.example.com/jwks"),
    )
    monkeypatch.setattr(
        "pykit_auth.oidc.httpx.AsyncClient", lambda timeout: FakeAsyncClient(malformed_jwks_response)
    )
    cache = JWKSCache("https://issuer.example.com/jwks", ttl_seconds=60)
    with pytest.raises(OIDCError, match="invalid JWKS payload"):
        await cache.get_keys()


@pytest.mark.asyncio
async def test_jwks_cache_and_id_token_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    private_key, private_pem = _rsa_keypair()
    public_key = private_key.public_key()
    jwks_response = httpx.Response(
        200,
        json={"keys": [_jwk(public_key, "kid-1")]},
        request=httpx.Request("GET", "https://issuer.example.com/jwks"),
    )
    monkeypatch.setattr("pykit_auth.oidc.httpx.AsyncClient", lambda timeout: FakeAsyncClient(jwks_response))

    cache = JWKSCache("https://issuer.example.com/jwks", ttl_seconds=60)
    validator = OIDCIDTokenValidator(
        OIDCClientConfig(
            issuer="https://issuer.example.com",
            client_id="client-1",
            redirect_uri="https://client.example.com/callback",
            client_type=OIDCClientType.PUBLIC,
        ),
        parse_discovery_document(_discovery()),
        cache,
    )
    token = jwt.encode(
        {
            "sub": "user-1",
            "iss": "https://issuer.example.com",
            "aud": "client-1",
            "nonce": "nonce-1",
            "iat": 1_700_000_000,
            "nbf": 1_700_000_000,
            "exp": 1_900_000_000,
        },
        private_pem,
        algorithm="RS256",
        headers={"kid": "kid-1"},
    )

    claims = await validator.validate(token, expected_nonce="nonce-1")
    assert claims["sub"] == "user-1"

    with pytest.raises(OIDCError, match="nonce mismatch"):
        await validator.validate(token, expected_nonce="wrong")


@pytest.mark.asyncio
async def test_jwks_cache_rejects_unknown_keys_and_invalid_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    invalid_response = httpx.Response(
        200,
        json={"not_keys": []},
        request=httpx.Request("GET", "https://issuer.example.com/jwks"),
    )
    monkeypatch.setattr(
        "pykit_auth.oidc.httpx.AsyncClient", lambda timeout: FakeAsyncClient(invalid_response)
    )
    cache = JWKSCache("https://issuer.example.com/jwks", ttl_seconds=60)
    with pytest.raises(OIDCError, match="invalid JWKS payload"):
        await cache.get_keys()

    valid_response = httpx.Response(
        200,
        json={"keys": []},
        request=httpx.Request("GET", "https://issuer.example.com/jwks"),
    )
    monkeypatch.setattr("pykit_auth.oidc.httpx.AsyncClient", lambda timeout: FakeAsyncClient(valid_response))
    await cache.invalidate()
    with pytest.raises(OIDCError, match="unknown signing key"):
        await cache.get_key("missing")

    with pytest.raises(ValueError, match="positive"):
        JWKSCache("https://issuer.example.com/jwks", ttl_seconds=0)

    with pytest.raises(ValueError, match="positive"):
        JWKSCache("https://issuer.example.com/jwks", http_timeout=0)
