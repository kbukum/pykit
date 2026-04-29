# pykit-encryption

Symmetric encryption utilities with AES-256-GCM and ChaCha20-Poly1305 backends.

## Installation

```bash
pip install pykit-encryption
# or
uv add pykit-encryption
```

## Quick Start

```python
from pykit_encryption import Algorithm, new_encryptor

# Factory function (defaults to AES-GCM)
enc = new_encryptor("my-secret-key")
ciphertext = enc.encrypt("sensitive data")
plaintext = enc.decrypt(ciphertext)

# ChaCha20-Poly1305
chacha = new_encryptor("my-secret-key", Algorithm.CHACHA20)
```

## Algorithms

| Algorithm | Enum | Best For |
|-----------|------|----------|
| AES-256-GCM (default) | `Algorithm.AES_GCM` | CPUs with AES-NI hardware acceleration |
| ChaCha20-Poly1305 | `Algorithm.CHACHA20` | CPUs without AES-NI (ARM, older x86) |

## Key Derivation

AES-GCM and ChaCha20-Poly1305 use **PBKDF2-SHA256** with:
- **600,000 iterations**
- **Random 16-byte salt** per encryption operation

## Ciphertext Format

```
base64(salt[16] || nonce[12] || ciphertext)
```

The salt is prepended so decryption can extract it and re-derive the key.

## Key Components

- **Encryptor** — Runtime-checkable protocol: `encrypt(plaintext) -> str` and `decrypt(ciphertext) -> str`
- **AESGCMEncryptor** — AES-256-GCM with PBKDF2-SHA256 key derivation
- **ChaCha20Encryptor** — ChaCha20-Poly1305 with PBKDF2-SHA256 key derivation
- **Algorithm** — Enum: `AES_GCM`, `CHACHA20`
- **new_encryptor(key, algorithm)** — Factory function creating an `Encryptor`

## Security Considerations

- Each encryption generates a unique random salt and nonce
- PBKDF2 with 600k iterations resists offline guessing better than raw hashing
- Both algorithms provide authenticated encryption
- The same plaintext encrypted twice produces different ciphertext

## Dependencies

- `cryptography` — Cryptographic primitives (AESGCM, ChaCha20Poly1305)

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — usage examples and test cases
