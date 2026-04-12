"""Tests for pykit_auth — JWT service and password hashing."""

from __future__ import annotations

import pytest

from pykit_auth import HashAlgorithm, JWTConfig, JWTService, PasswordHasher
from pykit_errors import InvalidInputError

# ---------------------------------------------------------------------------
# JWT Service
# ---------------------------------------------------------------------------


class TestJWTServiceRoundtrip:
    def test_generate_and_validate(self) -> None:
        svc = JWTService(JWTConfig(secret="test-secret-key-at-least-32-bytes!!"))
        token = svc.generate({"sub": "user-1"})
        claims = svc.validate(token)
        assert claims["sub"] == "user-1"
        assert "exp" in claims
        assert "iat" in claims

    def test_custom_claims_preserved(self) -> None:
        svc = JWTService(JWTConfig(secret="test-secret-key-at-least-32-bytes!!"))
        token = svc.generate({"sub": "u", "role": "admin", "tenant": "acme"})
        claims = svc.validate(token)
        assert claims["role"] == "admin"
        assert claims["tenant"] == "acme"

    def test_custom_ttl(self) -> None:
        svc = JWTService(JWTConfig(secret="test-secret-key-at-least-32-bytes!!"))
        token = svc.generate({"sub": "u"}, expires_in=60)
        claims = svc.validate(token)
        assert claims["exp"] - claims["iat"] == 60


class TestJWTServiceIssuerAudience:
    def test_issuer_audience_encoded(self) -> None:
        svc = JWTService(
            JWTConfig(secret="test-secret-key-at-least-32-bytes!!", issuer="myapp", audience="web")
        )
        token = svc.generate({"sub": "u"})
        claims = svc.validate(token)
        assert claims["iss"] == "myapp"
        assert claims["aud"] == "web"

    def test_wrong_issuer_rejected(self) -> None:
        svc_gen = JWTService(JWTConfig(secret="test-secret-key-at-least-32-bytes!!", issuer="app-a"))
        svc_val = JWTService(JWTConfig(secret="test-secret-key-at-least-32-bytes!!", issuer="app-b"))
        token = svc_gen.generate({"sub": "u"})
        with pytest.raises(InvalidInputError, match="invalid token"):
            svc_val.validate(token)

    def test_wrong_audience_rejected(self) -> None:
        svc_gen = JWTService(JWTConfig(secret="test-secret-key-at-least-32-bytes!!", audience="mobile"))
        svc_val = JWTService(JWTConfig(secret="test-secret-key-at-least-32-bytes!!", audience="web"))
        token = svc_gen.generate({"sub": "u"})
        with pytest.raises(InvalidInputError, match="invalid token"):
            svc_val.validate(token)


class TestJWTServiceErrors:
    def test_expired_token(self) -> None:
        svc = JWTService(JWTConfig(secret="test-secret-key-at-least-32-bytes!!"))
        token = svc.generate({"sub": "u"}, expires_in=-1)
        with pytest.raises(InvalidInputError, match="invalid token"):
            svc.validate(token)

    def test_invalid_token_string(self) -> None:
        svc = JWTService(JWTConfig(secret="test-secret-key-at-least-32-bytes!!"))
        with pytest.raises(InvalidInputError, match="invalid token"):
            svc.validate("not-a-jwt")

    def test_wrong_secret(self) -> None:
        svc_a = JWTService(JWTConfig(secret="test-secret-a-key-minimum-32-bytes!"))
        svc_b = JWTService(JWTConfig(secret="test-secret-b-key-minimum-32-bytes!"))
        token = svc_a.generate({"sub": "u"})
        with pytest.raises(InvalidInputError, match="invalid token"):
            svc_b.validate(token)


class TestJWTServiceDecodeUnverified:
    def test_decode_without_verification(self) -> None:
        svc = JWTService(JWTConfig(secret="test-secret-key-at-least-32-bytes!!"))
        token = svc.generate({"sub": "u", "debug": True})
        claims = svc.decode_unverified(token)
        assert claims["sub"] == "u"
        assert claims["debug"] is True

    def test_decode_unverified_bad_token(self) -> None:
        svc = JWTService(JWTConfig(secret="test-secret-key-at-least-32-bytes!!"))
        with pytest.raises(InvalidInputError, match="cannot decode"):
            svc.decode_unverified("garbage")


# ---------------------------------------------------------------------------
# Password Hasher
# ---------------------------------------------------------------------------


class TestPasswordHasherBcrypt:
    def test_hash_and_verify(self) -> None:
        hasher = PasswordHasher()
        hashed = hasher.hash("correct-horse-battery")
        assert hasher.verify("correct-horse-battery", hashed) is True

    def test_wrong_password_fails(self) -> None:
        hasher = PasswordHasher()
        hashed = hasher.hash("right")
        assert hasher.verify("wrong", hashed) is False

    def test_different_hashes_for_same_password(self) -> None:
        hasher = PasswordHasher()
        h1 = hasher.hash("same-password")
        h2 = hasher.hash("same-password")
        assert h1 != h2

    def test_bcrypt_prefix(self) -> None:
        hasher = PasswordHasher(algorithm=HashAlgorithm.BCRYPT)
        hashed = hasher.hash("test1234")
        assert hashed.startswith("$2")


class TestPasswordHasherArgon2:
    def test_hash_and_verify(self) -> None:
        hasher = PasswordHasher(algorithm=HashAlgorithm.ARGON2, rounds=1)
        hashed = hasher.hash("my-password")
        assert hasher.verify("my-password", hashed) is True

    def test_wrong_password_fails(self) -> None:
        hasher = PasswordHasher(algorithm=HashAlgorithm.ARGON2, rounds=1)
        hashed = hasher.hash("right")
        assert hasher.verify("wrong", hashed) is False

    def test_different_hashes_for_same_password(self) -> None:
        hasher = PasswordHasher(algorithm=HashAlgorithm.ARGON2, rounds=1)
        h1 = hasher.hash("same")
        h2 = hasher.hash("same")
        assert h1 != h2
