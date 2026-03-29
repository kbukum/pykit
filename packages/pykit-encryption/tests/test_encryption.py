"""Comprehensive tests for pykit-encryption."""

from __future__ import annotations

import base64

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.fernet import InvalidToken

from pykit_encryption import AESGCMEncryptor, Encryptor, FernetEncryptor, new_encryptor
from pykit_encryption.factory import Algorithm

# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocol:
    def test_aesgcm_is_encryptor(self) -> None:
        assert isinstance(AESGCMEncryptor("key"), Encryptor)

    def test_fernet_is_encryptor(self) -> None:
        assert isinstance(FernetEncryptor("key"), Encryptor)


# ---------------------------------------------------------------------------
# AES-GCM round-trip
# ---------------------------------------------------------------------------


class TestAESGCM:
    def test_roundtrip(self) -> None:
        enc = AESGCMEncryptor("my-secret")
        ct = enc.encrypt("hello world")
        assert enc.decrypt(ct) == "hello world"

    def test_empty_string(self) -> None:
        enc = AESGCMEncryptor("key")
        ct = enc.encrypt("")
        assert enc.decrypt(ct) == ""

    def test_unicode(self) -> None:
        enc = AESGCMEncryptor("key")
        text = "こんにちは 🌍"
        assert enc.decrypt(enc.encrypt(text)) == text

    def test_output_is_base64(self) -> None:
        enc = AESGCMEncryptor("key")
        ct = enc.encrypt("test")
        base64.standard_b64decode(ct)  # should not raise

    def test_different_keys_produce_different_ciphertext(self) -> None:
        ct1 = AESGCMEncryptor("key-a").encrypt("same")
        ct2 = AESGCMEncryptor("key-b").encrypt("same")
        assert ct1 != ct2

    def test_each_encrypt_is_unique(self) -> None:
        enc = AESGCMEncryptor("key")
        ct1 = enc.encrypt("same")
        ct2 = enc.encrypt("same")
        assert ct1 != ct2  # different nonces

    def test_tampered_ciphertext_fails(self) -> None:
        enc = AESGCMEncryptor("key")
        ct = enc.encrypt("hello")
        raw = bytearray(base64.standard_b64decode(ct))
        raw[-1] ^= 0xFF
        tampered = base64.standard_b64encode(bytes(raw)).decode()
        with pytest.raises(InvalidTag):
            enc.decrypt(tampered)

    def test_wrong_key_fails(self) -> None:
        ct = AESGCMEncryptor("key-a").encrypt("secret")
        with pytest.raises(InvalidTag):
            AESGCMEncryptor("key-b").decrypt(ct)

    def test_short_ciphertext_fails(self) -> None:
        enc = AESGCMEncryptor("key")
        short = base64.standard_b64encode(b"short").decode()
        with pytest.raises((ValueError, Exception)):
            enc.decrypt(short)


# ---------------------------------------------------------------------------
# Fernet round-trip
# ---------------------------------------------------------------------------


class TestFernet:
    def test_roundtrip(self) -> None:
        enc = FernetEncryptor("my-secret")
        ct = enc.encrypt("hello world")
        assert enc.decrypt(ct) == "hello world"

    def test_empty_string(self) -> None:
        enc = FernetEncryptor("key")
        ct = enc.encrypt("")
        assert enc.decrypt(ct) == ""

    def test_unicode(self) -> None:
        enc = FernetEncryptor("key")
        text = "こんにちは 🌍"
        assert enc.decrypt(enc.encrypt(text)) == text

    def test_different_keys_produce_different_ciphertext(self) -> None:
        ct1 = FernetEncryptor("key-a").encrypt("same")
        ct2 = FernetEncryptor("key-b").encrypt("same")
        assert ct1 != ct2

    def test_tampered_ciphertext_fails(self) -> None:
        enc = FernetEncryptor("key")
        ct = enc.encrypt("hello")
        raw = bytearray(ct.encode())
        raw[-1] = ord("A") if raw[-1] != ord("A") else ord("B")
        with pytest.raises(InvalidToken):
            enc.decrypt(bytes(raw).decode())

    def test_wrong_key_fails(self) -> None:
        ct = FernetEncryptor("key-a").encrypt("secret")
        with pytest.raises(InvalidToken):
            FernetEncryptor("key-b").decrypt(ct)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class TestFactory:
    def test_default_is_aesgcm(self) -> None:
        enc = new_encryptor("key")
        assert isinstance(enc, AESGCMEncryptor)

    def test_aesgcm_explicit(self) -> None:
        enc = new_encryptor("key", Algorithm.AES_GCM)
        assert isinstance(enc, AESGCMEncryptor)

    def test_fernet_explicit(self) -> None:
        enc = new_encryptor("key", Algorithm.FERNET)
        assert isinstance(enc, FernetEncryptor)

    def test_roundtrip_via_factory(self) -> None:
        for algo in Algorithm:
            enc = new_encryptor("test-key", algo)
            ct = enc.encrypt("payload")
            assert enc.decrypt(ct) == "payload"

    def test_invalid_algorithm(self) -> None:
        with pytest.raises(ValueError, match="unsupported algorithm"):
            new_encryptor("key", "bogus")  # type: ignore[arg-type]
