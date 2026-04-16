"""Tests for pykit_auth_apikey — API key generation, hashing, and comparison."""

from __future__ import annotations

from unittest.mock import patch

from pykit_auth_apikey import compare_hash, generate, hash_key


class TestCompareHashValid:
    def test_matching_key_returns_true(self) -> None:
        result = generate(prefix="sk_")
        assert compare_hash(result.plain_key, result.key_hash) is True

    def test_matching_raw_hash(self) -> None:
        plain = "my-secret-api-key"
        hashed = hash_key(plain)
        assert compare_hash(plain, hashed) is True


class TestCompareHashInvalid:
    def test_wrong_key_returns_false(self) -> None:
        result = generate(prefix="sk_")
        assert compare_hash("wrong-key", result.key_hash) is False

    def test_wrong_hash_returns_false(self) -> None:
        result = generate()
        assert compare_hash(result.plain_key, "badhash") is False

    def test_empty_key_returns_false(self) -> None:
        result = generate()
        assert compare_hash("", result.key_hash) is False


class TestCompareHashTimingSafe:
    def test_uses_hmac_compare_digest(self) -> None:
        result = generate(prefix="test_")
        with patch("pykit_auth_apikey.apikey.hmac.compare_digest", return_value=True) as mock_cmp:
            compare_hash(result.plain_key, result.key_hash)
            mock_cmp.assert_called_once()
