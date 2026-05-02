"""OIDC discovery, PKCE authorization, JWKS caching, and refresh rotation."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import secrets
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from time import monotonic
from typing import cast
from urllib.parse import parse_qsl, urlencode, urlparse

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import ec, ed448, ed25519, rsa

from pykit_auth.jwt import JWTAlgorithm
from pykit_errors import InvalidInputError

type TokenResponseValue = str | int | float | bool | None
type TokenResponseData = dict[str, TokenResponseValue]
type VerificationKey = (
    rsa.RSAPublicKey
    | ec.EllipticCurvePublicKey
    | ed25519.Ed25519PublicKey
    | ed448.Ed448PublicKey
    | str
    | bytes
)

_LOGGER = logging.getLogger(__name__)
_OIDC_SIGNING_ALGORITHMS = {JWTAlgorithm.RS256.value, JWTAlgorithm.ES256.value, JWTAlgorithm.EDDSA.value}


class OIDCClientType(StrEnum):
    """OIDC client types."""

    PUBLIC = "public"
    CONFIDENTIAL = "confidential"


@dataclass(frozen=True, slots=True)
class OIDCDiscoveryDocument:
    """Validated OIDC discovery metadata."""

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    response_types_supported: tuple[str, ...] = ("code",)
    code_challenge_methods_supported: tuple[str, ...] = ("S256",)
    id_token_signing_alg_values_supported: tuple[str, ...] = ("RS256", "ES256", "EdDSA")

    def __post_init__(self) -> None:
        _validate_https_url(self.issuer, field_name="issuer")
        _validate_https_url(self.authorization_endpoint, field_name="authorization_endpoint")
        _validate_https_url(self.token_endpoint, field_name="token_endpoint")
        _validate_https_url(self.jwks_uri, field_name="jwks_uri")
        if "code" not in self.response_types_supported:
            raise ValueError("response_types_supported must include 'code'")
        if "S256" not in self.code_challenge_methods_supported:
            raise ValueError("code_challenge_methods_supported must include 'S256'")
        if not set(self.id_token_signing_alg_values_supported).intersection(_OIDC_SIGNING_ALGORITHMS):
            raise ValueError("OIDC signing algorithms must include at least one of RS256, ES256, EdDSA")


@dataclass(frozen=True, slots=True)
class OIDCClientConfig:
    """OIDC client configuration."""

    issuer: str
    client_id: str
    redirect_uri: str
    client_type: OIDCClientType = OIDCClientType.PUBLIC
    client_secret: str | None = None
    default_scopes: tuple[str, ...] = ("openid",)
    leeway_seconds: int = 30

    def __post_init__(self) -> None:
        _validate_https_url(self.issuer, field_name="issuer")
        _validate_redirect_uri(self.redirect_uri)
        if "*" in self.redirect_uri:
            raise ValueError("redirect_uri must be an exact URI, not a wildcard")
        if not self.client_id:
            raise ValueError("client_id is required")
        if self.client_type is OIDCClientType.CONFIDENTIAL and not self.client_secret:
            raise ValueError("confidential clients require client_secret")
        if not 0 <= self.leeway_seconds <= 60:
            raise ValueError("leeway_seconds must be between 0 and 60")


@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    """OIDC authorization request with PKCE and anti-CSRF state."""

    url: str
    state: str
    nonce: str
    code_verifier: str
    code_challenge: str
    scopes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RefreshConfig:
    """OIDC refresh token exchange configuration."""

    token_endpoint: str
    client_id: str
    refresh_token: str
    client_secret: str | None = None
    scopes: tuple[str, ...] = ()
    extra_params: dict[str, str] = field(default_factory=dict)
    require_refresh_rotation: bool = True
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        _validate_https_url(self.token_endpoint, field_name="token_endpoint")
        if not self.client_id:
            raise ValueError("client_id is required")
        if not self.refresh_token:
            raise ValueError("refresh_token is required")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


@dataclass(frozen=True, slots=True)
class TokenResult:
    """Tokens returned from an OIDC exchange."""

    access_token: str
    refresh_token: str = ""
    id_token: str = ""
    token_type: str = "Bearer"
    expires_at: datetime | None = None
    scopes: tuple[str, ...] = ()


class OIDCError(InvalidInputError):
    """Raised on OIDC validation failures."""


def parse_discovery_document(document: Mapping[str, object] | str | bytes) -> OIDCDiscoveryDocument:
    """Parse and validate an OIDC discovery document."""

    if isinstance(document, Mapping):
        payload = document
    else:
        raw = document.decode("utf-8") if isinstance(document, bytes) else document
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OIDCError("invalid OIDC discovery document") from exc
        if not isinstance(parsed, dict):
            raise OIDCError("invalid OIDC discovery document")
        payload = parsed

    try:
        response_types = _string_tuple(payload.get("response_types_supported", ["code"]))
        code_challenge_methods = _string_tuple(payload.get("code_challenge_methods_supported", ["S256"]))
        signing_algs = _string_tuple(
            payload.get("id_token_signing_alg_values_supported", ["RS256", "ES256", "EdDSA"])
        )
        return OIDCDiscoveryDocument(
            issuer=_require_string(payload, "issuer"),
            authorization_endpoint=_require_string(payload, "authorization_endpoint"),
            token_endpoint=_require_string(payload, "token_endpoint"),
            jwks_uri=_require_string(payload, "jwks_uri"),
            response_types_supported=response_types,
            code_challenge_methods_supported=code_challenge_methods,
            id_token_signing_alg_values_supported=signing_algs,
        )
    except (TypeError, ValueError) as exc:
        raise OIDCError("invalid OIDC discovery document") from exc


def generate_code_verifier(length: int = 64) -> str:
    """Generate a PKCE code verifier."""

    if length < 43 or length > 128:
        raise ValueError("PKCE code verifier length must be between 43 and 128")
    return secrets.token_urlsafe(length)[:length]


def build_code_challenge(code_verifier: str) -> str:
    """Build an RFC 7636 S256 code challenge."""

    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def build_authorization_request(
    discovery: OIDCDiscoveryDocument,
    config: OIDCClientConfig,
    *,
    code_verifier: str | None,
    scopes: Sequence[str] | None = None,
    state: str | None = None,
    nonce: str | None = None,
) -> AuthorizationRequest:
    """Build an authorization URL with mandatory PKCE for public clients."""

    effective_scopes = tuple(scopes or config.default_scopes)
    if "openid" not in effective_scopes:
        raise OIDCError("openid scope is required")
    if config.client_type is OIDCClientType.PUBLIC and not code_verifier:
        raise OIDCError("PKCE code_verifier is required for public clients")
    if code_verifier is None:
        code_verifier = generate_code_verifier()

    effective_state = state or secrets.token_urlsafe(24)
    effective_nonce = nonce or secrets.token_urlsafe(24)
    query = urlencode(
        {
            "response_type": "code",
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "scope": " ".join(effective_scopes),
            "state": effective_state,
            "nonce": effective_nonce,
            "code_challenge": build_code_challenge(code_verifier),
            "code_challenge_method": "S256",
        }
    )
    return AuthorizationRequest(
        url=f"{discovery.authorization_endpoint}?{query}",
        state=effective_state,
        nonce=effective_nonce,
        code_verifier=code_verifier,
        code_challenge=build_code_challenge(code_verifier),
        scopes=effective_scopes,
    )


def validate_callback(
    *, expected_state: str, received_state: str, expected_nonce: str, id_token_claims: Mapping[str, object]
) -> None:
    """Validate callback state and nonce."""

    if not hmac.compare_digest(expected_state, received_state):
        raise OIDCError("OIDC state mismatch")
    nonce = id_token_claims.get("nonce")
    if not isinstance(nonce, str) or not hmac.compare_digest(expected_nonce, nonce):
        raise OIDCError("OIDC nonce mismatch")


class JWKSCache:
    """Asynchronous JWKS cache with bounded refresh on key rotation."""

    def __init__(
        self,
        jwks_uri: str,
        *,
        ttl_seconds: int = 3600,
        http_timeout: float = 10.0,
        min_refresh_interval_seconds: int = 30,
    ) -> None:
        _validate_https_url(jwks_uri, field_name="jwks_uri")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if http_timeout <= 0:
            raise ValueError("http_timeout must be positive")
        if min_refresh_interval_seconds <= 0:
            raise ValueError("min_refresh_interval_seconds must be positive")
        self._jwks_uri = jwks_uri
        self._ttl_seconds = ttl_seconds
        self._http_timeout = http_timeout
        self._min_refresh_interval_seconds = min_refresh_interval_seconds
        self._keys: dict[str, dict[str, object]] = {}
        self._fetched_at = 0.0
        self._last_forced_refresh_at = 0.0
        self._lock = asyncio.Lock()

    async def get_key(self, kid: str) -> VerificationKey:
        """Return a signing key for *kid*, refreshing once on cache miss."""

        keys = await self.get_keys()
        if kid in keys:
            return cast("VerificationKey", jwt.PyJWK.from_dict(keys[kid]).key)
        await self._refresh(force=True)
        keys = await self.get_keys()
        if kid not in keys:
            raise OIDCError("unknown signing key")
        return cast("VerificationKey", jwt.PyJWK.from_dict(keys[kid]).key)

    async def get_keys(self) -> dict[str, dict[str, object]]:
        """Return cached JWKS entries keyed by ``kid``."""

        if monotonic() - self._fetched_at > self._ttl_seconds:
            await self._refresh()
        return dict(self._keys)

    async def invalidate(self) -> None:
        """Expire the cache immediately."""

        async with self._lock:
            self._fetched_at = 0.0

    async def _refresh(self, *, force: bool = False) -> None:
        async with self._lock:
            now = monotonic()
            if not force and now - self._fetched_at <= self._ttl_seconds:
                return
            if force and now - self._last_forced_refresh_at < self._min_refresh_interval_seconds:
                return
            if force:
                self._last_forced_refresh_at = now

            async with httpx.AsyncClient(timeout=self._http_timeout) as client:
                response = await client.get(self._jwks_uri)
                response.raise_for_status()
                try:
                    payload = response.json()
                except (json.JSONDecodeError, TypeError, ValueError) as exc:
                    raise OIDCError("invalid JWKS payload") from exc
            if not isinstance(payload, dict):
                raise OIDCError("invalid JWKS payload")
            keys = payload.get("keys")
            if not isinstance(keys, list):
                raise OIDCError("invalid JWKS payload")

            parsed: dict[str, dict[str, object]] = {}
            for key in keys:
                if not isinstance(key, dict):
                    raise OIDCError("invalid JWKS payload")
                kid = key.get("kid")
                if not isinstance(kid, str) or not kid:
                    raise OIDCError("invalid JWKS payload")
                parsed[kid] = key

            self._keys = parsed
            self._fetched_at = monotonic()


class OIDCIDTokenValidator:
    """Validate OIDC ID tokens against discovery metadata and JWKS."""

    def __init__(
        self,
        config: OIDCClientConfig,
        discovery: OIDCDiscoveryDocument,
        jwks_cache: JWKSCache,
    ) -> None:
        self._config = config
        self._discovery = discovery
        self._jwks_cache = jwks_cache

    async def validate(self, id_token: str, *, expected_nonce: str) -> dict[str, object]:
        """Validate *id_token* and return claims."""

        try:
            header = jwt.get_unverified_header(id_token)
        except jwt.PyJWTError as exc:
            raise OIDCError("invalid ID token") from exc

        algorithm = header.get("alg")
        if not isinstance(algorithm, str) or algorithm not in _OIDC_SIGNING_ALGORITHMS:
            raise OIDCError("invalid ID token")
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise OIDCError("invalid ID token")

        key = await self._jwks_cache.get_key(kid)
        try:
            claims = jwt.decode(
                id_token,
                key,
                algorithms=[algorithm],
                issuer=self._discovery.issuer,
                audience=self._config.client_id,
                leeway=timedelta(seconds=self._config.leeway_seconds),
                options={"require": ["exp", "iat", "nbf", "iss", "aud", "nonce"]},
            )
        except jwt.PyJWTError as exc:
            raise OIDCError("invalid ID token") from exc

        nonce = claims.get("nonce")
        if not isinstance(nonce, str) or not hmac.compare_digest(expected_nonce, nonce):
            raise OIDCError("OIDC nonce mismatch")
        return claims


async def refresh_token(
    config: RefreshConfig,
    *,
    client: httpx.AsyncClient | None = None,
) -> TokenResult:
    """Exchange a refresh token for new credentials."""

    form: dict[str, str] = {
        "grant_type": "refresh_token",
        "client_id": config.client_id,
        "refresh_token": config.refresh_token,
    }
    if config.client_secret:
        form["client_secret"] = config.client_secret
    if config.scopes:
        form["scope"] = " ".join(config.scopes)
    form.update(config.extra_params)

    own_client = client is None
    active_client = client or httpx.AsyncClient(timeout=config.timeout_seconds)
    try:
        response = await active_client.post(
            config.token_endpoint,
            data=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    except httpx.HTTPError as exc:
        raise OIDCError("sending refresh request failed") from exc
    finally:
        if own_client:
            await active_client.aclose()

    if response.status_code != 200:
        _LOGGER.debug("OIDC refresh rejected by provider", extra={"status_code": response.status_code})
        raise OIDCError("OIDC refresh request failed")

    result = _parse_token_response(response.content)
    if config.require_refresh_rotation and (
        not result.refresh_token or result.refresh_token == config.refresh_token
    ):
        raise OIDCError("refresh token rotation is required")
    return result


def _parse_token_response(body: bytes) -> TokenResult:
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict):
        return _build_token_result(parsed)

    decoded = body.decode("utf-8", errors="ignore")
    try:
        parsed_pairs = parse_qsl(decoded, keep_blank_values=True, strict_parsing=True)
    except ValueError as exc:
        raise OIDCError("invalid token response") from exc
    if not parsed_pairs:
        raise OIDCError("invalid token response")
    payload: TokenResponseData = dict(parsed_pairs)
    return _build_token_result(payload)


def _build_token_result(payload: Mapping[str, TokenResponseValue]) -> TokenResult:
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise OIDCError("invalid token response")

    refresh_token = payload.get("refresh_token")
    id_token = payload.get("id_token")
    token_type = payload.get("token_type")
    scope = payload.get("scope")
    expires_in = payload.get("expires_in")
    expires_at: datetime | None = None
    if isinstance(expires_in, int) and expires_in > 0:
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
    elif isinstance(expires_in, str) and expires_in.isdigit():
        expires_at = datetime.now(UTC) + timedelta(seconds=int(expires_in))

    scopes: tuple[str, ...] = ()
    if isinstance(scope, str) and scope:
        scopes = tuple(part for part in scope.split(" ") if part)

    return TokenResult(
        access_token=access_token,
        refresh_token=refresh_token if isinstance(refresh_token, str) else "",
        id_token=id_token if isinstance(id_token, str) else "",
        token_type=token_type if isinstance(token_type, str) and token_type else "Bearer",
        expires_at=expires_at,
        scopes=scopes,
    )


def _require_string(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} is required")
    return value


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError("expected list")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("expected list[str]")
        result.append(item)
    return tuple(result)


def _validate_https_url(value: str, *, field_name: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"{field_name} must be an https URL")


def _validate_redirect_uri(value: str) -> None:
    parsed = urlparse(value)
    localhost = parsed.hostname in {"localhost", "127.0.0.1"}
    if parsed.scheme not in {"https", "http"}:
        raise ValueError("redirect_uri must use https or localhost http")
    if parsed.scheme == "http" and not localhost:
        raise ValueError("redirect_uri must use https unless it targets localhost")
    if not parsed.netloc:
        raise ValueError("redirect_uri must be absolute")
