# pykit-security

TLS configuration helpers for Python's `ssl` module with separate client and server context builders.

## Installation

```bash
pip install pykit-security
# or
uv add pykit-security
```

## Quick Start

```python
from pykit_security import TLSConfig

# Client-side TLS with mutual authentication
tls = TLSConfig(
    ca_file="/certs/ca.pem",
    cert_file="/certs/client.pem",
    key_file="/certs/client-key.pem",
    min_version=ssl.TLSVersion.TLSv1_2,
)
tls.validate()  # Raises ValueError/FileNotFoundError on bad config
ssl_ctx = tls.build()  # Returns ssl.SSLContext or None if not enabled

# Server-side TLS
server_ctx = tls.build_server()  # Returns server-mode ssl.SSLContext

# Skip verification for development
dev_tls = TLSConfig(skip_verify=True)
dev_ctx = dev_tls.build()
```

## Key Components

- **TLSConfig** — Dataclass with `ca_file`, `cert_file`, `key_file`, `server_hostname`, `skip_verify`, and `min_version` fields
  - **build()** — Create a client-side `ssl.SSLContext` (returns `None` if no TLS settings configured)
  - **build_server()** — Create a server-side `ssl.SSLContext` with `CERT_REQUIRED` when CA is provided
  - **validate()** — Check configuration consistency (cert/key pairing, file existence)
  - **is_enabled()** — Returns `True` if any TLS setting is configured

## Dependencies

- `pykit-errors`

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
