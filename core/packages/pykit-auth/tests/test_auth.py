"""Tests for JWT and password primitives."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa

from pykit_auth import (
    HashAlgorithm,
    JWTAlgorithm,
    JWTConfig,
    JWTService,
    PasswordHasher,
    PasswordHashPolicy,
)
from pykit_errors import InvalidInputError


def _rsa_keypair() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    return private_pem, public_pem


def _eddsa_keypair() -> tuple[str, str]:
    private_key = ed25519.Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    return private_pem, public_pem


def _hs256_service(secret: str = "x" * 32) -> JWTService:
    return JWTService(
        JWTConfig(
            issuer="pykit-tests",
            audience="pykit-clients",
            algorithm=JWTAlgorithm.HS256,
            shared_secret=secret,
            allow_internal_hs256=True,
        )
    )


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


class TestJWTService:
    def test_rs256_roundtrip_is_default(self) -> None:
        private_key, public_key = _rsa_keypair()
        service = JWTService(
            JWTConfig(
                issuer="pykit-tests",
                audience="pykit-clients",
                private_key=private_key,
                public_key=public_key,
            )
        )

        token = service.generate({"sub": "user-1", "role": "admin"})
        claims = service.validate(token)

        assert service.config.algorithm is JWTAlgorithm.RS256
        assert claims["sub"] == "user-1"
        assert claims["iss"] == "pykit-tests"
        assert claims["aud"] == "pykit-clients"
        assert "nbf" in claims

    def test_eddsa_roundtrip(self) -> None:
        private_key, public_key = _eddsa_keypair()
        service = JWTService(
            JWTConfig(
                issuer="pykit-tests",
                audience="pykit-clients",
                algorithm=JWTAlgorithm.EDDSA,
                private_key=private_key,
                public_key=public_key,
            )
        )

        token = service.generate({"sub": "user-2"})
        assert service.validate(token)["sub"] == "user-2"

    def test_hs256_requires_explicit_opt_in(self) -> None:
        with pytest.raises(ValueError, match="internal-only"):
            JWTConfig(
                issuer="pykit-tests",
                audience="pykit-clients",
                algorithm=JWTAlgorithm.HS256,
                shared_secret="x" * 32,
            )

    def test_hs256_roundtrip_when_explicit(self) -> None:
        service = _hs256_service()
        token = service.generate({"sub": "user-1"})
        assert service.validate(token)["sub"] == "user-1"

    def test_algorithm_confusion_is_rejected(self) -> None:
        private_key, public_key = _rsa_keypair()
        service = JWTService(
            JWTConfig(
                issuer="pykit-tests",
                audience="pykit-clients",
                private_key=private_key,
                public_key=public_key,
            )
        )
        header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode("utf-8"))
        payload = _b64url(
            json.dumps(
                {
                    "sub": "admin",
                    "iss": "pykit-tests",
                    "aud": "pykit-clients",
                    "iat": int(time.time()),
                    "nbf": int(time.time()),
                    "exp": int(time.time()) + 3600,
                }
            ).encode("utf-8")
        )
        signature = _b64url(
            hmac.new(public_key.encode("utf-8"), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        )
        forged = f"{header}.{payload}.{signature}"

        with pytest.raises(InvalidInputError, match="invalid token"):
            service.validate(forged)

    def test_alg_none_is_rejected(self) -> None:
        payload = {
            "sub": "admin",
            "iss": "pykit-tests",
            "aud": "pykit-clients",
            "iat": int(time.time()),
            "nbf": int(time.time()),
            "exp": int(time.time()) + 60,
        }
        forged = jwt.encode(payload, "", algorithm="none")

        with pytest.raises(InvalidInputError, match="invalid token"):
            _hs256_service().validate(forged)

    def test_missing_required_claim_is_rejected(self) -> None:
        private_key, public_key = _rsa_keypair()
        service = JWTService(
            JWTConfig(
                issuer="pykit-tests",
                audience="pykit-clients",
                private_key=private_key,
                public_key=public_key,
            )
        )
        token = jwt.encode(
            {"sub": "user-1", "iss": "pykit-tests", "aud": "pykit-clients", "iat": int(time.time())},
            private_key,
            algorithm="RS256",
        )

        with pytest.raises(InvalidInputError, match="invalid token"):
            service.validate(token)

    def test_decode_unverified_is_diagnostic_only(self) -> None:
        service = _hs256_service()
        token = service.generate({"sub": "user-1", "role": "viewer"})
        claims = service.decode_unverified(token)
        assert claims["role"] == "viewer"

    def test_wrong_audience_is_rejected(self) -> None:
        service = _hs256_service()
        token = service.generate({"sub": "user-1"})
        validator = JWTService(
            JWTConfig(
                issuer="pykit-tests",
                audience="other-clients",
                algorithm=JWTAlgorithm.HS256,
                shared_secret="x" * 32,
                allow_internal_hs256=True,
            )
        )

        with pytest.raises(InvalidInputError, match="invalid token"):
            validator.validate(token)

    def test_jwt_config_validation(self) -> None:
        private_key, public_key = _rsa_keypair()

        with pytest.raises(ValueError, match="issuer is required"):
            JWTConfig(issuer="", audience="pykit-clients", private_key=private_key, public_key=public_key)

        with pytest.raises(ValueError, match="audience is required"):
            JWTConfig(issuer="pykit-tests", audience="", private_key=private_key, public_key=public_key)

        with pytest.raises(ValueError, match="32 bytes"):
            JWTConfig(
                issuer="pykit-tests",
                audience="pykit-clients",
                algorithm=JWTAlgorithm.HS256,
                shared_secret="short",
                allow_internal_hs256=True,
            )

        with pytest.raises(ValueError, match="shared_secret"):
            JWTConfig(
                issuer="pykit-tests",
                audience="pykit-clients",
                private_key=private_key,
                shared_secret="x" * 32,
            )

        with pytest.raises(ValueError, match="default_ttl"):
            JWTConfig(
                issuer="pykit-tests",
                audience="pykit-clients",
                private_key=private_key,
                public_key=public_key,
                default_ttl=0,
            )

        with pytest.raises(ValueError, match="between 0 and 60"):
            JWTConfig(
                issuer="pykit-tests",
                audience="pykit-clients",
                private_key=private_key,
                public_key=public_key,
                leeway_seconds=61,
            )

        with pytest.raises(ValueError, match="cannot be combined"):
            JWTConfig(
                issuer="pykit-tests",
                audience="pykit-clients",
                algorithm=JWTAlgorithm.HS256,
                shared_secret="x" * 32,
                private_key=private_key,
                allow_internal_hs256=True,
            )

        with pytest.raises(ValueError, match="requires a private_key or public_key"):
            JWTConfig(issuer="pykit-tests", audience="pykit-clients")

    def test_generate_rejects_claim_override_conflicts(self) -> None:
        service = _hs256_service()
        with pytest.raises(InvalidInputError, match="issuer must match"):
            service.generate({"iss": "other"})

        with pytest.raises(InvalidInputError, match="audience must match"):
            service.generate({"aud": "other"})

    def test_decode_unverified_rejects_malformed_shape(self) -> None:
        with pytest.raises(InvalidInputError, match="invalid token"):
            _hs256_service().validate("missing-separators")

        with pytest.raises(InvalidInputError, match="cannot decode token"):
            _hs256_service().decode_unverified("a.b.c")

    def test_public_key_only_config_cannot_sign(self) -> None:
        _, public_key = _rsa_keypair()
        service = JWTService(
            JWTConfig(
                issuer="pykit-tests",
                audience="pykit-clients",
                public_key=public_key,
            )
        )

        with pytest.raises(InvalidInputError, match="signing key"):
            service.generate({"sub": "user-1"})

    def test_private_key_only_config_can_verify_and_key_id_mismatch_rejects(self) -> None:
        private_key, _public_key = _rsa_keypair()
        service = JWTService(
            JWTConfig(
                issuer="pykit-tests",
                audience="pykit-clients",
                private_key=private_key,
                key_id="kid-1",
            )
        )
        token = service.generate({"sub": "user-1"})
        assert service.validate(token)["sub"] == "user-1"

        tampered = jwt.encode(
            {
                "sub": "user-1",
                "iss": "pykit-tests",
                "aud": "pykit-clients",
                "iat": int(time.time()),
                "nbf": int(time.time()),
                "exp": int(time.time()) + 3600,
            },
            private_key,
            algorithm="RS256",
            headers={"kid": "other"},
        )
        with pytest.raises(InvalidInputError, match="invalid token"):
            service.validate(tampered)


class TestPasswordHasher:
    def test_argon2id_is_default(self) -> None:
        hasher = PasswordHasher()
        hashed = hasher.hash("correct horse battery staple")
        assert hashed.startswith("$argon2id$")
        assert hasher.verify("correct horse battery staple", hashed)
        assert hasher.policy.default_algorithm is HashAlgorithm.ARGON2ID

    def test_bcrypt_fallback_verifies_and_needs_rehash(self) -> None:
        bcrypt_hasher = PasswordHasher(PasswordHashPolicy(default_algorithm=HashAlgorithm.BCRYPT))
        argon_hasher = PasswordHasher()

        hashed = bcrypt_hasher.hash("migrate-me")

        assert argon_hasher.verify("migrate-me", hashed)
        assert argon_hasher.needs_rehash(hashed) is True

    def test_invalid_hash_is_rejected(self) -> None:
        assert PasswordHasher().verify("password", "not-a-password-hash") is False

    def test_policy_enforces_group05_minimums(self) -> None:
        with pytest.raises(ValueError, match="65536"):
            PasswordHashPolicy(memory_cost_kib=1024)

        with pytest.raises(ValueError, match="at least 12"):
            PasswordHashPolicy(default_algorithm=HashAlgorithm.BCRYPT, bcrypt_rounds=10)

    def test_bcrypt_policy_can_issue_hashes(self) -> None:
        hasher = PasswordHasher(PasswordHashPolicy(default_algorithm=HashAlgorithm.BCRYPT))
        hashed = hasher.hash("legacy-password")
        assert hashed.startswith("$2")
        assert hasher.needs_rehash(hashed) is False

    def test_needs_rehash_for_invalid_hash(self) -> None:
        assert PasswordHasher().needs_rehash("invalid") is True

    def test_needs_rehash_for_invalid_argon_prefix(self) -> None:
        assert PasswordHasher().needs_rehash("$argon2id$invalid") is True
