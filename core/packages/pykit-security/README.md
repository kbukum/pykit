# pykit-security

TLS, HTTP header, CORS, and verification helpers for secure-by-default services.

## Installation

```bash
pip install pykit-security
# or
uv add pykit-security
```

## Quick start

```python
from pykit_security import CORSConfig, SecurityHeadersPolicy, TLSConfig, extract_bearer_token

tls = TLSConfig(
    ca_file="/certs/ca.pem",
    cert_file="/certs/client.pem",
    key_file="/certs/client-key.pem",
)
headers = SecurityHeadersPolicy().build_headers(tls_enabled=tls.is_enabled())
cors_headers = CORSConfig(allowed_origins=("https://app.example.com",)).build_preflight_headers(
    "https://app.example.com"
)
token = extract_bearer_token({"Authorization": "Bearer secret-token"})
```

## Core APIs

- **`TLSConfig`** builds client and server TLS contexts with a TLS 1.3 default and TLS 1.2 floor.
- **`SecurityHeadersPolicy`** produces secure response headers such as CSP, HSTS, referrer, and permissions policies.
- **`CORSConfig`** enforces exact-match origins and builds preflight headers.
- **`extract_bearer_token()`** reads bearer tokens from headers and rejects query-string tokens.
- **`McpHttpSecurityConfig`** and **`OAuthPkceConfig`** model MCP-over-HTTP and PKCE-related settings.
- **`Verifier`** and **`VerificationResult`** define signature verification seams.

## Security notes

- Token extraction is **header-only**. Query parameters such as `access_token` and `id_token` are rejected.
- `CORSConfig` denies requests unless the origin exactly matches `allowed_origins`.
- `SecurityHeadersPolicy` only emits HSTS when `tls_enabled=True`.

## See also

- [Main pykit README](../../../README.md)
- [tests/](tests/)
