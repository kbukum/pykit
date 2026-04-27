# pykit-auth-apikey

API key generation, hashing, validation, and rotation with grace periods.

## Installation

```bash
pip install pykit-auth-apikey
```

## Quick start

```python
from pykit_auth_apikey import ApiKeyService, ApiKeyConfig

service = ApiKeyService(config=ApiKeyConfig())
key = await service.generate(owner_id="user-123", label="my-app")

# Validate incoming key
result = await service.validate(raw_key="pk_live_...")
if result.valid:
    print(f"Key belongs to: {result.owner_id}")
```

## Features

- Secure key generation with configurable prefix and entropy
- BLAKE2/PBKDF2 hashing — plaintext key never stored
- Rotation with grace periods for zero-downtime key replacement
- Scoped keys with expiry and revocation support
- Async-first API
