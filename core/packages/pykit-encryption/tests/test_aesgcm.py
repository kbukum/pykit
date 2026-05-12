"""Tests for AES-256-GCM encryption backend."""

from __future__ import annotations

import base64

import pytest
from cryptography.exceptions import InvalidTag

from pykit_encryption import AESGCMEncryptor


class TestAESGCMEncryptor:
    """AES-256-GCM encryption tests."""

    def test_encrypt_decrypt_roundtrip(self) -> None:
        enc = AESGCMEncryptor("my-secret-key")
        ct = enc.encrypt("hello world")
        assert enc.decrypt(ct) == "hello world"

    def test_different_keys_cannot_decrypt(self) -> None:
        ct = AESGCMEncryptor("key-a").encrypt("secret")
        with pytest.raises(InvalidTag):
            AESGCMEncryptor("key-b").decrypt(ct)

    def test_corrupted_ciphertext_fails(self) -> None:
        enc = AESGCMEncryptor("key")
        ct = enc.encrypt("hello")
        raw = bytearray(base64.standard_b64decode(ct))
        raw[-1] ^= 0xFF
        tampered = base64.standard_b64encode(bytes(raw)).decode()
        with pytest.raises(InvalidTag):
            enc.decrypt(tampered)

    def test_empty_plaintext(self) -> None:
        enc = AESGCMEncryptor("key")
        ct = enc.encrypt("")
        assert enc.decrypt(ct) == ""

    def test_unicode_roundtrip(self) -> None:
        enc = AESGCMEncryptor("key")
        text = "こんにちは 🌍"
        assert enc.decrypt(enc.encrypt(text)) == text

    def test_each_encrypt_produces_different_output(self) -> None:
        enc = AESGCMEncryptor("key")
        ct1 = enc.encrypt("same")
        ct2 = enc.encrypt("same")
        assert ct1 != ct2

    def test_output_is_valid_base64(self) -> None:
        enc = AESGCMEncryptor("key")
        ct = enc.encrypt("test")
        base64.standard_b64decode(ct)  # should not raise

    def test_ciphertext_contains_salt_nonce_data(self) -> None:
        enc = AESGCMEncryptor("key")
        ct = enc.encrypt("test")
        raw = base64.standard_b64decode(ct)
        # salt(16) + nonce(12) + ciphertext (at least auth tag 16 bytes)
        assert len(raw) >= 16 + 12 + 16

    def test_short_ciphertext_fails(self) -> None:
        enc = AESGCMEncryptor("key")
        short = base64.standard_b64encode(b"short").decode()
        with pytest.raises((ValueError, Exception)):
            enc.decrypt(short)
