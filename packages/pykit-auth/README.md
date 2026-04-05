# pykit-auth

JWT authentication and password hashing with bcrypt and scrypt support.

## Installation

```bash
pip install pykit-auth
# or
uv add pykit-auth
```

## Quick Start

```python
from pykit_auth import JWTConfig, JWTService, PasswordHasher, HashAlgorithm

# JWT token generation and validation
config = JWTConfig(secret="my-secret", issuer="my-app", default_ttl=3600)
jwt = JWTService(config)

token = jwt.generate({"user_id": "abc", "role": "admin"})
claims = jwt.validate(token)
print(claims["user_id"])  # "abc"

# Password hashing (bcrypt by default)
hasher = PasswordHasher()
hashed = hasher.hash("my-password")
assert hasher.verify("my-password", hashed)
```

## Key Components

- **JWTConfig** — Configuration dataclass for JWT signing (secret, algorithm, issuer, audience, TTL)
- **JWTService** — JWT token generation and validation implementing `TokenValidator` and `TokenGenerator` protocols; supports `generate()`, `validate()`, and `decode_unverified()`
- **TokenValidator** — Protocol defining `validate(token) -> dict` for pluggable token validation
- **TokenGenerator** — Protocol defining `generate(claims, expires_in) -> str` for pluggable token creation
- **PasswordHasher** — Password hashing and verification with configurable rounds
- **HashAlgorithm** — StrEnum with `BCRYPT` and `ARGON2` (scrypt-based) algorithms

## Dependencies

- `pyjwt` — JWT encoding/decoding
- `bcrypt` — Password hashing
- `pykit-errors` — Error types (`InvalidInputError` on validation failure)

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
