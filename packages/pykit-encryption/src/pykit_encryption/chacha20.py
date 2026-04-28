"""ChaCha20-Poly1305 encryption backend.

Uses PBKDF2-SHA256 key derivation (600,000 iterations, random 16-byte salt).
Ciphertext format: base64(salt[16] || nonce[12] || ciphertext).
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_SALT_SIZE = 16
_NONCE_SIZE = 12
_PBKDF2_ITERATIONS = 600_000
_KEY_LEN = 32


class ChaCha20Encryptor:
    """ChaCha20-Poly1305 authenticated encryption with PBKDF2-SHA256 key derivation."""

    def __init__(self, key: str) -> None:
        self._passphrase = key.encode()

    def _derive_key(self, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=_KEY_LEN,
            salt=salt,
            iterations=_PBKDF2_ITERATIONS,
        )
        return kdf.derive(self._passphrase)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext and return base64-encoded ciphertext."""
        salt = os.urandom(_SALT_SIZE)
        key = self._derive_key(salt)
        nonce = os.urandom(_NONCE_SIZE)
        ct = ChaCha20Poly1305(key).encrypt(nonce, plaintext.encode(), None)
        return base64.standard_b64encode(salt + nonce + ct).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt base64-encoded ciphertext and return plaintext."""
        data = base64.standard_b64decode(ciphertext)
        if len(data) < _SALT_SIZE + _NONCE_SIZE:
            raise ValueError("ciphertext too short")
        salt = data[:_SALT_SIZE]
        nonce = data[_SALT_SIZE : _SALT_SIZE + _NONCE_SIZE]
        ct = data[_SALT_SIZE + _NONCE_SIZE :]
        key = self._derive_key(salt)
        return ChaCha20Poly1305(key).decrypt(nonce, ct, None).decode()
