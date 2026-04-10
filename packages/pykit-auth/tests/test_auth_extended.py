"""Extended security tests for pykit-auth — JWT and password hashing."""

from __future__ import annotations

import base64
import json
import threading

import pytest

from pykit_auth import HashAlgorithm, JWTConfig, JWTService, PasswordHasher
from pykit_errors import InvalidInputError

# ---------------------------------------------------------------------------
# JWT — Algorithm Mismatch
# ---------------------------------------------------------------------------


class TestJWTAlgorithmMismatch:
    def test_hs256_token_rejected_by_hs384_validator(self) -> None:
        svc_gen = JWTService(JWTConfig(secret="shared-secret", algorithm="HS256"))
        svc_val = JWTService(JWTConfig(secret="shared-secret", algorithm="HS384"))
        token = svc_gen.generate({"sub": "u"})
        with pytest.raises(InvalidInputError, match="invalid token"):
            svc_val.validate(token)

    def test_hs512_token_rejected_by_hs256_validator(self) -> None:
        svc_gen = JWTService(JWTConfig(secret="shared-secret", algorithm="HS512"))
        svc_val = JWTService(JWTConfig(secret="shared-secret", algorithm="HS256"))
        token = svc_gen.generate({"sub": "u"})
        with pytest.raises(InvalidInputError, match="invalid token"):
            svc_val.validate(token)


# ---------------------------------------------------------------------------
# JWT — Token Format Attacks
# ---------------------------------------------------------------------------


class TestJWTTokenFormats:
    def test_empty_string_rejected(self) -> None:
        svc = JWTService(JWTConfig(secret="s"))
        with pytest.raises(InvalidInputError, match="invalid token"):
            svc.validate("")

    def test_whitespace_rejected(self) -> None:
        svc = JWTService(JWTConfig(secret="s"))
        with pytest.raises(InvalidInputError, match="invalid token"):
            svc.validate("   ")

    def test_no_dots_rejected(self) -> None:
        svc = JWTService(JWTConfig(secret="s"))
        with pytest.raises(InvalidInputError, match="invalid token"):
            svc.validate("nodots")

    def test_tampered_payload(self) -> None:
        svc = JWTService(JWTConfig(secret="s"))
        token = svc.generate({"sub": "user-1", "role": "user"})
        # Tamper with the payload segment
        parts = token.split(".")
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))
        payload["role"] = "admin"
        tampered_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
        tampered = f"{parts[0]}.{tampered_payload}.{parts[2]}"
        with pytest.raises(InvalidInputError, match="invalid token"):
            svc.validate(tampered)


# ---------------------------------------------------------------------------
# JWT — Claims Edge Cases
# ---------------------------------------------------------------------------


class TestJWTClaimsEdgeCases:
    def test_empty_claims_dict(self) -> None:
        svc = JWTService(JWTConfig(secret="s"))
        token = svc.generate({})
        claims = svc.validate(token)
        assert "exp" in claims
        assert "iat" in claims

    def test_large_payload(self) -> None:
        svc = JWTService(JWTConfig(secret="s"))
        big_data = {"key": "x" * 50000}
        token = svc.generate(big_data)
        claims = svc.validate(token)
        assert len(claims["key"]) == 50000

    def test_special_characters_in_claims(self) -> None:
        svc = JWTService(JWTConfig(secret="s"))
        token = svc.generate({"sub": "用户", "emoji": "🔑", "html": "<b>&amp;</b>"})
        claims = svc.validate(token)
        assert claims["sub"] == "用户"
        assert claims["emoji"] == "🔑"

    def test_negative_ttl_expires_immediately(self) -> None:
        svc = JWTService(JWTConfig(secret="s"))
        token = svc.generate({"sub": "u"}, expires_in=-10)
        with pytest.raises(InvalidInputError, match="invalid token"):
            svc.validate(token)

    def test_zero_ttl(self) -> None:
        svc = JWTService(JWTConfig(secret="s"))
        token = svc.generate({"sub": "u"}, expires_in=0)
        # 0-second TTL means exp == iat, should be expired by now
        with pytest.raises(InvalidInputError, match="invalid token"):
            svc.validate(token)


# ---------------------------------------------------------------------------
# JWT — decode_unverified
# ---------------------------------------------------------------------------


class TestJWTDecodeUnverified:
    def test_corrupted_token(self) -> None:
        svc = JWTService(JWTConfig(secret="s"))
        with pytest.raises(InvalidInputError, match="cannot decode"):
            svc.decode_unverified("x.y.z")

    def test_wrong_secret_still_decodes(self) -> None:
        svc_a = JWTService(JWTConfig(secret="secret-a"))
        svc_b = JWTService(JWTConfig(secret="secret-b"))
        token = svc_a.generate({"sub": "u", "role": "admin"})
        claims = svc_b.decode_unverified(token)
        assert claims["sub"] == "u"
        assert claims["role"] == "admin"


# ---------------------------------------------------------------------------
# JWT — Config Validation
# ---------------------------------------------------------------------------


class TestJWTConfigEdgeCases:
    def test_empty_secret_still_signs(self) -> None:
        # PyJWT allows empty secret for HS256 — this is a known behavior
        svc = JWTService(JWTConfig(secret=""))
        token = svc.generate({"sub": "u"})
        assert token  # it generates, but should this be allowed?

    def test_no_issuer_audience_optional(self) -> None:
        svc = JWTService(JWTConfig(secret="s"))
        token = svc.generate({"sub": "u"})
        claims = svc.validate(token)
        assert "iss" not in claims
        assert "aud" not in claims


# ---------------------------------------------------------------------------
# Password Hasher — Extended
# ---------------------------------------------------------------------------


class TestPasswordHasherBcryptExtended:
    def test_empty_password(self) -> None:
        hasher = PasswordHasher()
        # bcrypt accepts empty passwords — verify it round-trips
        hashed = hasher.hash("")
        assert hasher.verify("", hashed) is True

    def test_unicode_password(self) -> None:
        hasher = PasswordHasher()
        pw = "пароль-密码-🔑"
        hashed = hasher.hash(pw)
        assert hasher.verify(pw, hashed) is True

    def test_very_long_password_rejected(self) -> None:
        hasher = PasswordHasher()
        # bcrypt rejects passwords > 72 bytes
        pw = "a" * 100
        with pytest.raises(ValueError):
            hasher.hash(pw)

    def test_malformed_hash_returns_false(self) -> None:
        hasher = PasswordHasher()
        assert hasher.verify("password", "not-a-hash") is False

    def test_empty_hash_returns_false(self) -> None:
        hasher = PasswordHasher()
        assert hasher.verify("password", "") is False

    def test_different_rounds(self) -> None:
        hasher = PasswordHasher(rounds=4)
        hashed = hasher.hash("test-password")
        assert hasher.verify("test-password", hashed) is True


class TestPasswordHasherArgon2Extended:
    def test_empty_password(self) -> None:
        hasher = PasswordHasher(algorithm=HashAlgorithm.ARGON2, rounds=1)
        hashed = hasher.hash("")
        assert hasher.verify("", hashed) is True

    def test_unicode_password(self) -> None:
        hasher = PasswordHasher(algorithm=HashAlgorithm.ARGON2, rounds=1)
        pw = "contraseña-パスワード"
        hashed = hasher.hash(pw)
        assert hasher.verify(pw, hashed) is True

    def test_malformed_hash_returns_false(self) -> None:
        hasher = PasswordHasher(algorithm=HashAlgorithm.ARGON2, rounds=1)
        assert hasher.verify("password", "not-a-hash") is False

    def test_hash_without_dollar_sign(self) -> None:
        hasher = PasswordHasher(algorithm=HashAlgorithm.ARGON2, rounds=1)
        assert hasher.verify("password", "nodollarsign") is False

    def test_corrupt_hex_in_hash(self) -> None:
        hasher = PasswordHasher(algorithm=HashAlgorithm.ARGON2, rounds=1)
        assert hasher.verify("password", "ZZZZ$XXXX") is False


# ---------------------------------------------------------------------------
# Password Hasher — Cross-algorithm safety
# ---------------------------------------------------------------------------


class TestPasswordHasherCrossAlgorithm:
    def test_bcrypt_hash_fails_argon2_verify(self) -> None:
        bcrypt_h = PasswordHasher(algorithm=HashAlgorithm.BCRYPT)
        argon2_h = PasswordHasher(algorithm=HashAlgorithm.ARGON2, rounds=1)
        hashed = bcrypt_h.hash("password")
        assert argon2_h.verify("password", hashed) is False

    def test_argon2_hash_fails_bcrypt_verify(self) -> None:
        argon2_h = PasswordHasher(algorithm=HashAlgorithm.ARGON2, rounds=1)
        bcrypt_h = PasswordHasher(algorithm=HashAlgorithm.BCRYPT)
        hashed = argon2_h.hash("password")
        assert bcrypt_h.verify("password", hashed) is False


# ---------------------------------------------------------------------------
# Concurrency Safety
# ---------------------------------------------------------------------------


class TestConcurrency:
    def test_concurrent_bcrypt_hash(self) -> None:
        hasher = PasswordHasher(rounds=4)
        errors: list[Exception] = []
        results: list[str] = []
        lock = threading.Lock()

        def hash_and_verify() -> None:
            try:
                h = hasher.hash("concurrent-test")
                assert hasher.verify("concurrent-test", h)
                with lock:
                    results.append(h)
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=hash_and_verify) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"concurrent errors: {errors}"
        # All hashes should be unique (unique salts)
        assert len(set(results)) == len(results)

    def test_concurrent_jwt_generate_validate(self) -> None:
        svc = JWTService(JWTConfig(secret="concurrent-secret"))
        errors: list[Exception] = []

        def gen_and_validate(i: int) -> None:
            try:
                token = svc.generate({"sub": f"user-{i}"})
                claims = svc.validate(token)
                assert claims["sub"] == f"user-{i}"
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=gen_and_validate, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"concurrent errors: {errors}"
