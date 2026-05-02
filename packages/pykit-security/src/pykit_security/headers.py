"""Security header and token extraction policies."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pykit_errors import InvalidInputError


@dataclass(frozen=True, slots=True)
class SecurityHeadersPolicy:
    """Secure-by-default HTTP response headers."""

    content_security_policy: str = (
        "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; object-src 'none'"
    )
    permissions_policy: str = "camera=(), geolocation=(), microphone=()"
    referrer_policy: str = "strict-origin-when-cross-origin"
    frame_options: str = "DENY"
    content_type_options: str = "nosniff"
    strict_transport_security: str = "max-age=63072000; includeSubDomains; preload"
    cross_origin_opener_policy: str = "same-origin"

    def build_headers(self, *, tls_enabled: bool) -> dict[str, str]:
        """Build security headers."""

        headers = {
            "Content-Security-Policy": self.content_security_policy,
            "Permissions-Policy": self.permissions_policy,
            "Referrer-Policy": self.referrer_policy,
            "X-Frame-Options": self.frame_options,
            "X-Content-Type-Options": self.content_type_options,
            "Cross-Origin-Opener-Policy": self.cross_origin_opener_policy,
        }
        if tls_enabled:
            headers["Strict-Transport-Security"] = self.strict_transport_security
        return headers


@dataclass(frozen=True, slots=True)
class CORSConfig:
    """Exact-match CORS policy."""

    allowed_origins: tuple[str, ...] = ()
    allow_credentials: bool = False
    allow_methods: tuple[str, ...] = ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
    allow_headers: tuple[str, ...] = ("Authorization", "Content-Type", "X-API-Key")
    max_age_seconds: int = 600

    def __post_init__(self) -> None:
        if self.max_age_seconds < 0:
            raise ValueError("max_age_seconds must be non-negative")

    def build_preflight_headers(self, origin: str, request_headers: Sequence[str] = ()) -> dict[str, str]:
        """Build CORS headers for *origin*."""

        if self.allowed_origins and origin not in self.allowed_origins:
            raise InvalidInputError("origin not allowed")
        allowed_headers = tuple(dict.fromkeys([*self.allow_headers, *request_headers]))
        headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": ", ".join(self.allow_methods),
            "Access-Control-Allow-Headers": ", ".join(allowed_headers),
            "Vary": "Origin",
        }
        if self.allow_credentials:
            headers["Access-Control-Allow-Credentials"] = "true"
        if self.max_age_seconds:
            headers["Access-Control-Max-Age"] = str(self.max_age_seconds)
        return headers


def extract_bearer_token(
    headers: Mapping[str, str],
    *,
    query_params: Mapping[str, str] | None = None,
    header_name: str = "authorization",
) -> str:
    """Extract a bearer token from headers and reject query-string tokens."""

    if query_params and any(key in query_params for key in ("access_token", "token", "id_token")):
        raise InvalidInputError("tokens in query parameters are forbidden")

    candidates = {key.lower(): value for key, value in headers.items()}
    authorization = candidates.get(header_name.lower(), "")
    scheme, separator, token = authorization.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not token:
        raise InvalidInputError("missing bearer token")
    return token
