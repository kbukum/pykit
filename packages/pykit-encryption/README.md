# pykit-encryption

Symmetric encryption utilities with AES-256-GCM and Fernet backends, mirroring gokit/encryption.

## Installation

```bash
pip install pykit-encryption
# or
uv add pykit-encryption
```

## Quick Start

```python
from pykit_encryption import new_encryptor, Algorithm, AESGCMEncryptor

# Factory function (defaults to AES-GCM)
enc = new_encryptor("my-secret-key")
ciphertext = enc.encrypt("sensitive data")
plaintext = enc.decrypt(ciphertext)

# Explicit algorithm selection
fernet_enc = new_encryptor("my-secret-key", Algorithm.FERNET)
ct = fernet_enc.encrypt("hello world")

# Direct class usage
aes = AESGCMEncryptor("my-secret-key")
ct = aes.encrypt("hello")  # base64-encoded, random nonce per call
```

## Key Components

- **Encryptor** — Runtime-checkable protocol defining `encrypt(plaintext) -> str` and `decrypt(ciphertext) -> str` with base64-encoded I/O
- **AESGCMEncryptor** — AES-256-GCM authenticated encryption; SHA-256 derived key, random 12-byte nonce prepended to ciphertext
- **FernetEncryptor** — Fernet (AES-128-CBC + HMAC-SHA256) encryption; SHA-256 derived key, higher-level API
- **Algorithm** — Enum: `AES_GCM`, `FERNET`
- **new_encryptor(key, algorithm)** — Factory function creating an `Encryptor` for the given algorithm (defaults to AES-GCM)

## Dependencies

- `cryptography` — Cryptographic primitives (AESGCM, Fernet)

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
