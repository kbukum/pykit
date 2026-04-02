"""OAuth2 token refresh implementation mirroring gokit/auth/oidc/refresh.go."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs

import httpx

from pykit_auth_oidc.types import RefreshConfig, TokenResult


class RefreshError(Exception):
    """Raised when a token refresh request fails."""

    def __init__(self, message: str, *, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


async def refresh_token(
    config: RefreshConfig,
    *,
    client: httpx.AsyncClient | None = None,
) -> TokenResult:
    """Exchange a refresh token for new access + refresh tokens.

    Supports both JSON and form-encoded response formats for compatibility
    with different OAuth2 providers.

    Args:
        config: Refresh configuration with endpoint, credentials, and token.
        client: Optional httpx.AsyncClient; a default one is created if omitted.

    Returns:
        TokenResult with the new tokens.

    Raises:
        RefreshError: If the request fails or the response is invalid.
    """
    if not config.token_endpoint:
        raise RefreshError("token endpoint is required")
    if not config.refresh_token:
        raise RefreshError("refresh token is required")

    form: dict[str, str] = {
        "grant_type": "refresh_token",
        "client_id": config.client_id,
        "refresh_token": config.refresh_token,
    }
    if config.client_secret:
        form["client_secret"] = config.client_secret
    if config.scopes:
        form["scope"] = " ".join(config.scopes)
    for k, v in config.extra_params.items():
        form[k] = v

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient()

    try:
        resp = await client.post(
            config.token_endpoint,
            data=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    except httpx.HTTPError as exc:
        raise RefreshError(f"sending refresh request: {exc}") from exc
    finally:
        if own_client:
            await client.aclose()

    if resp.status_code != 200:
        raise RefreshError(
            f"refresh failed (status {resp.status_code}): {resp.text}",
            status_code=resp.status_code,
        )

    return _parse_token_response(resp.content)


def _parse_token_response(body: bytes) -> TokenResult:
    """Parse a token response body, trying JSON first then form-encoded."""
    # Try JSON first — most OAuth2 providers return JSON.
    try:
        data = json.loads(body)
        if isinstance(data, dict) and data.get("access_token"):
            return _build_result(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token", ""),
                id_token=data.get("id_token", ""),
                token_type=data.get("token_type", ""),
                expires_in=data.get("expires_in", 0),
                scope=data.get("scope", ""),
            )
    except (json.JSONDecodeError, KeyError):
        pass

    # Fall back to form-encoded (e.g., older Facebook API).
    try:
        values = parse_qs(body.decode(), keep_blank_values=True)
        access_token = values.get("access_token", [""])[0]
        if not access_token:
            raise RefreshError("no access_token in response")

        expires_in_str = values.get("expires_in", ["0"])[0]
        try:
            expires_in = int(expires_in_str)
        except ValueError:
            expires_in = 0

        return _build_result(
            access_token=access_token,
            refresh_token=values.get("refresh_token", [""])[0],
            id_token=values.get("id_token", [""])[0],
            token_type=values.get("token_type", [""])[0],
            expires_in=expires_in,
            scope=values.get("scope", [""])[0],
        )
    except Exception as exc:
        raise RefreshError("unable to parse token response") from exc


def _build_result(
    *,
    access_token: str,
    refresh_token: str,
    id_token: str,
    token_type: str,
    expires_in: int,
    scope: str,
) -> TokenResult:
    """Build a TokenResult from raw parsed fields."""
    result = TokenResult(
        access_token=access_token,
        refresh_token=refresh_token,
        id_token=id_token,
        token_type=token_type or "Bearer",
    )
    if expires_in and expires_in > 0:
        result.expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
    if scope:
        result.scopes = scope.split(" ")
    return result
