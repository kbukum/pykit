"""Tests for encryption factory and algorithm dispatch."""

from __future__ import annotations

import pytest

from pykit_encryption import (
    AESGCMEncryptor,
    Algorithm,
    ChaCha20Encryptor,
    Encryptor,
    new_encryptor,
)


class TestFactory:
    """Factory dispatch tests."""

    def test_default_is_aesgcm(self) -> None:
        enc = new_encryptor("key")
        assert isinstance(enc, AESGCMEncryptor)

    def test_aesgcm_explicit(self) -> None:
        enc = new_encryptor("key", Algorithm.AES_GCM)
        assert isinstance(enc, AESGCMEncryptor)

    def test_chacha20_explicit(self) -> None:
        enc = new_encryptor("key", Algorithm.CHACHA20)
        assert isinstance(enc, ChaCha20Encryptor)

    def test_roundtrip_all_algorithms(self) -> None:
        for algo in Algorithm:
            enc = new_encryptor("test-key", algo)
            ct = enc.encrypt("payload")
            assert enc.decrypt(ct) == "payload", f"Failed for {algo}"

    def test_invalid_algorithm(self) -> None:
        with pytest.raises(ValueError, match="unsupported algorithm"):
            new_encryptor("key", "bogus")  # type: ignore[arg-type]

    def test_all_implementations_are_encryptors(self) -> None:
        assert isinstance(AESGCMEncryptor("k"), Encryptor)
        assert isinstance(ChaCha20Encryptor("k"), Encryptor)

    def test_cross_algorithm_incompatibility(self) -> None:
        """Ciphertext from one algorithm cannot be decrypted by another."""
        enc1 = new_encryptor("same-key", Algorithm.AES_GCM)
        enc2 = new_encryptor("same-key", Algorithm.CHACHA20)
        ct = enc1.encrypt("test")
        with pytest.raises(Exception):  # noqa: B017
            enc2.decrypt(ct)
