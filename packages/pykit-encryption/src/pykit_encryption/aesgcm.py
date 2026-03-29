"""AES-256-GCM encryption backend.

Mirrors gokit's ``encryption.Service``: the user-supplied key is hashed with
SHA-256 to produce a 32-byte key, a random 12-byte nonce is prepended to the
ciphertext, and the result is base64-encoded.
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class AESGCMEncryptor:
    """AES-256-GCM authenticated encryption."""

    _NONCE_SIZE = 12  # 96-bit nonce recommended for AES-GCM

    def __init__(self, key: str) -> None:
        key_bytes = hashlib.sha256(key.encode()).digest()
        self._aesgcm = AESGCM(key_bytes)

    def encrypt(self, plaintext: str) -> str:
        nonce = os.urandom(self._NONCE_SIZE)
        ct = self._aesgcm.encrypt(nonce, plaintext.encode(), None)
        return base64.standard_b64encode(nonce + ct).decode()

    def decrypt(self, ciphertext: str) -> str:
        data = base64.standard_b64decode(ciphertext)
        if len(data) < self._NONCE_SIZE:
            raise ValueError("ciphertext too short")
        nonce, ct = data[: self._NONCE_SIZE], data[self._NONCE_SIZE :]
        return self._aesgcm.decrypt(nonce, ct, None).decode()
