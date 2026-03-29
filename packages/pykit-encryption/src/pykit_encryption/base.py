"""Encryptor protocol — the contract all encryption backends implement."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Encryptor(Protocol):
    """Symmetric encrypt / decrypt with string I/O."""

    def encrypt(self, plaintext: str) -> str:
        """Encrypt *plaintext* and return a base64-encoded ciphertext string."""
        ...

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a base64-encoded *ciphertext* string and return the original plaintext."""
        ...
