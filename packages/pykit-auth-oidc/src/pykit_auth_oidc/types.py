"""OAuth2/OIDC data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RefreshConfig:
    """Configuration for a token refresh request.

    Args:
        token_endpoint: OAuth2 token endpoint URL.
        client_id: OAuth2 client identifier.
        client_secret: OAuth2 client secret (may be empty for public clients).
        refresh_token: The refresh token to exchange.
        scopes: Optional set of scopes to request.
        extra_params: Optional platform-specific parameters.
    """

    token_endpoint: str
    client_id: str
    client_secret: str = ""
    refresh_token: str = ""
    scopes: list[str] = field(default_factory=list)
    extra_params: dict[str, str] = field(default_factory=dict)


@dataclass
class TokenResult:
    """Tokens returned from an OAuth2/OIDC token exchange.

    Args:
        access_token: The new access token.
        refresh_token: The new refresh token (may be empty).
        id_token: Raw OIDC ID token JWT string (empty for non-OIDC).
        token_type: Typically "Bearer".
        expires_at: When the access token expires.
        scopes: Granted scopes (may differ from requested).
    """

    access_token: str
    refresh_token: str = ""
    id_token: str = ""
    token_type: str = "Bearer"
    expires_at: datetime | None = None
    scopes: list[str] = field(default_factory=list)
