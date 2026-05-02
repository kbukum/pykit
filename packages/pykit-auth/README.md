# pykit-auth

JWT, API key, OIDC, and password authentication primitives with Argon2id defaults.

## Installation

```bash
pip install pykit-auth
# or
uv add pykit-auth
```

## Quick Start

```python
from pykit_auth import (
    APIKeyHashingConfig,
    APIKeyHasher,
    JWTConfig,
    JWTService,
    PasswordHasher,
)

jwt_service = JWTService(
    JWTConfig(
        issuer="my-app",
        audience="my-clients",
        private_key=PRIVATE_KEY_PEM,
        public_key=PUBLIC_KEY_PEM,
    )
)
token = jwt_service.generate({"sub": "user-1"})
claims = jwt_service.validate(token)

hasher = PasswordHasher()
hashed = hasher.hash("my-password")
assert hasher.verify("my-password", hashed)

apikey_hasher = APIKeyHasher(APIKeyHashingConfig(pepper="x" * 32))
issued = apikey_hasher.generate_key("pk")
```

## Key Components

- **JWTConfig / JWTService** — RS256-first JWT signing and verification; HS256 is explicit internal-only fallback
- **APIKeyHasher / APIKeyManager** — Prefix-based API key issuance, HMAC-SHA-256 hashing with pepper, rotation, and ASGI middleware
- **OIDC** — discovery parsing, PKCE request building, JWKS caching, refresh rotation, and ID token validation
- **PasswordHasher** — Argon2id default hashing with bcrypt migration fallback

## Dependencies

- `pyjwt` — JWT encoding/decoding
- `argon2-cffi` — Argon2id password hashing
- `bcrypt` — Password migration fallback
- `httpx` — OIDC discovery/JWKS/refresh transport
- `cryptography` — JWT signing keys and JWKS handling
- `pykit-errors` — Error types (`InvalidInputError` on validation failure)

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
