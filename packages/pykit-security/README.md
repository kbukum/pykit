# pykit-security

TLS, secure headers, CORS, and bearer-token extraction policies.

## Installation

```bash
pip install pykit-security
# or
uv add pykit-security
```

## Quick Start

```python
from pykit_security import CORSConfig, SecurityHeadersPolicy, TLSConfig, extract_bearer_token

tls = TLSConfig(
    ca_file="/certs/ca.pem",
    cert_file="/certs/client.pem",
    key_file="/certs/client-key.pem",
)
headers = SecurityHeadersPolicy().build_headers(tls_enabled=True)
cors_headers = CORSConfig(allowed_origins=("https://app.example.com",)).build_preflight_headers(
    "https://app.example.com"
)
token = extract_bearer_token({"Authorization": "Bearer eyJ..."})
```

## Key Components

- **TLSConfig** — TLS 1.3-default client/server context builder with TLS 1.2 floor
- **SecurityHeadersPolicy** — Secure-by-default HSTS/CSP/referrer/permissions headers
- **CORSConfig** — Exact-match CORS preflight policy
- **extract_bearer_token()** — Header-only bearer extraction that rejects query-string tokens

## Dependencies

- `pykit-errors`

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
