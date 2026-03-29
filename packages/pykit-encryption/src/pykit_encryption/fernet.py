"""Fernet encryption backend.

Provides a simpler, higher-level alternative to raw AES-GCM.  The user-
supplied key is hashed with SHA-256 and the digest is base64url-encoded to
produce the 32-byte Fernet key (Fernet requires a url-safe-base64-encoded
32-byte key).
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet


class FernetEncryptor:
    """Fernet (AES-128-CBC + HMAC-SHA256) encryption."""

    def __init__(self, key: str) -> None:
        key_bytes = hashlib.sha256(key.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        self._fernet = Fernet(fernet_key)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode()).decode()
