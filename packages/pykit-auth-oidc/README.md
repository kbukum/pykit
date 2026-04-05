# pykit-auth-oidc

Async OAuth2/OIDC token refresh client with support for JSON and form-encoded providers.

## Installation

```bash
pip install pykit-auth-oidc
# or
uv add pykit-auth-oidc
```

## Quick Start

```python
import asyncio
from pykit_auth_oidc import RefreshConfig, refresh_token

config = RefreshConfig(
    token_endpoint="https://auth.example.com/oauth2/token",
    client_id="my-client-id",
    client_secret="my-client-secret",
    refresh_token="current-refresh-token",
    scopes=["openid", "profile"],
)

async def main():
    result = await refresh_token(config)
    print(result.access_token)
    print(result.expires_at)  # datetime or None
    print(result.scopes)      # granted scopes

asyncio.run(main())
```

## Key Components

- **RefreshConfig** — Configuration dataclass with token endpoint, client credentials, scopes, and extra params for platform-specific needs
- **TokenResult** — Response dataclass containing `access_token`, `refresh_token`, `id_token`, `token_type`, `expires_at`, and `scopes`
- **refresh_token()** — Async function that exchanges a refresh token for new access/refresh tokens; accepts an optional `httpx.AsyncClient` for connection reuse
- **RefreshError** — Exception raised on refresh failure with `status_code` attribute for HTTP error handling

## Dependencies

- `httpx` — Async HTTP client

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
