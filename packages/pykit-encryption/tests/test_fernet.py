"""Tests for Fernet encryption backend."""

from __future__ import annotations

import pytest
from cryptography.fernet import InvalidToken

from pykit_encryption import FernetEncryptor


class TestFernetEncryptor:
    """Fernet encryption tests.

    Note: Fernet is Python-specific and not mirrored in gokit or rskit.
    """

    def test_encrypt_decrypt_roundtrip(self) -> None:
        enc = FernetEncryptor("my-secret-key")
        ct = enc.encrypt("hello world")
        assert enc.decrypt(ct) == "hello world"

    def test_different_keys_cannot_decrypt(self) -> None:
        ct = FernetEncryptor("key-a").encrypt("secret")
        with pytest.raises(InvalidToken):
            FernetEncryptor("key-b").decrypt(ct)

    def test_corrupted_ciphertext_fails(self) -> None:
        enc = FernetEncryptor("key")
        ct = enc.encrypt("hello")
        raw = bytearray(ct.encode())
        raw[-1] = ord("A") if raw[-1] != ord("A") else ord("B")
        with pytest.raises(InvalidToken):
            enc.decrypt(bytes(raw).decode())

    def test_empty_plaintext(self) -> None:
        enc = FernetEncryptor("key")
        ct = enc.encrypt("")
        assert enc.decrypt(ct) == ""

    def test_unicode_roundtrip(self) -> None:
        enc = FernetEncryptor("key")
        text = "こんにちは 🌍"
        assert enc.decrypt(enc.encrypt(text)) == text

    def test_each_encrypt_produces_different_output(self) -> None:
        enc = FernetEncryptor("key")
        ct1 = enc.encrypt("same")
        ct2 = enc.encrypt("same")
        assert ct1 != ct2
