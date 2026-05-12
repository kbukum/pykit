"""MCP Streamable HTTP security helper models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class McpHttpSecurityConfig:
    """Secure-by-default MCP Streamable HTTP settings."""

    bind_host: str = "127.0.0.1"
    max_payload_bytes: int = 1_048_576
    allowed_origins: tuple[str, ...] = ()
    require_oauth_pkce: bool = True
    jwt_algorithms: tuple[str, ...] = ("RS256", "ES256")

    def validate(self) -> None:
        if self.bind_host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError(
                "MCP HTTP servers must bind to loopback addresses; external binds are not supported"
            )
        if self.max_payload_bytes <= 0:
            raise ValueError("max_payload_bytes must be positive")
        if "none" in {alg.lower() for alg in self.jwt_algorithms}:
            raise ValueError("JWT alg 'none' is forbidden")


@dataclass(frozen=True, slots=True)
class OAuthPkceConfig:
    """OAuth 2.1 + PKCE helper configuration."""

    issuer: str
    audience: str
    redirect_uris: tuple[str, ...] = field(default_factory=tuple)
    code_challenge_methods: tuple[str, ...] = ("S256",)
