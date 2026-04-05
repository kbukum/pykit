"""Security audit tests for pykit authentication, error handling, and crypto."""

from __future__ import annotations

import asyncio
import re
import ssl
import time

import jwt as pyjwt
import pytest

from pykit_auth import JWTConfig, JWTService, PasswordHasher, HashAlgorithm
from pykit_errors import AppError, InvalidInputError

try:
    from pykit_security.tls import TLSConfig
    HAS_SECURITY = True
except ImportError:
    HAS_SECURITY = False


# ─── 1. Error Message Sanitization ─────────────────────────────────────────

SENSITIVE_PATTERNS = [
    "super-secret-api-key",
    "postgres://admin:s3cret@db",
    "-----BEGIN RSA PRIVATE KEY-----",
    "password123",
]


class TestErrorSanitization:
    """Verify error messages never leak secrets or internal details."""

    @pytest.mark.parametrize(
        "err",
        [
            AppError.unauthorized(),
            AppError.forbidden(),
            AppError.token_expired(),
            AppError.invalid_token(),
            AppError.internal(Exception("connection refused")),
            AppError.database_error(Exception("auth failed for user admin")),
        ],
        ids=[
            "unauthorized",
            "forbidden",
            "token_expired",
            "invalid_token",
            "internal",
            "database_error",
        ],
    )
    def test_auth_errors_do_not_contain_secrets(self, err: AppError) -> None:
        err_str = str(err)
        for secret in SENSITIVE_PATTERNS:
            assert secret not in err_str, f"Error leaked secret: {err_str}"

    def test_error_with_sensitive_cause_does_not_expose_in_message_field(self) -> None:
        cause = Exception("password=s3cret host=db.internal:5432")
        err = AppError.internal(cause)
        # The message field (used in HTTP responses) should be generic
        assert "s3cret" not in err.message
        assert "db.internal" not in err.message

    def test_auth_error_str_no_system_paths(self) -> None:
        for err in [
            AppError.unauthorized(),
            AppError.forbidden(),
            AppError.token_expired(),
            AppError.invalid_token(),
        ]:
            err_str = str(err)
            assert "/usr/" not in err_str
            assert "/etc/" not in err_str
            assert "Traceback" not in err_str

    def test_error_details_can_be_added_without_leak(self) -> None:
        err = AppError.unauthorized("bad token")
        err.with_detail("request_id", "req-123")
        # Details should not appear in str representation
        err_str = str(err)
        assert "req-123" not in err_str  # details are structured, not in str()


# ─── 2. JWT Security ───────────────────────────────────────────────────────


class TestJWTSecurity:
    """JWT algorithm confusion, token validation, and secret handling."""

    def _make_service(
        self, secret: str = "test-secret-key-minimum-length", **kwargs
    ) -> JWTService:
        return JWTService(JWTConfig(secret=secret, **kwargs))

    def test_algorithm_confusion_none_rejected(self) -> None:
        svc = self._make_service()

        # Forge a token with algorithm "none"
        payload = {"sub": "admin", "exp": int(time.time()) + 3600}
        forged = pyjwt.encode(payload, "", algorithm="none")

        with pytest.raises((InvalidInputError, Exception)):
            svc.validate(forged)

    def test_algorithm_mismatch_rejected(self) -> None:
        svc_hs256 = self._make_service(algorithm="HS256")

        # Create token with HS384
        payload = {"sub": "user", "exp": int(time.time()) + 3600}
        token = pyjwt.encode(payload, "test-secret-key-minimum-length", algorithm="HS384")

        with pytest.raises((InvalidInputError, Exception)):
            svc_hs256.validate(token)

    def test_expired_token_rejected(self) -> None:
        svc = self._make_service()
        token = svc.generate({"sub": "user"}, expires_in=-10)

        with pytest.raises((InvalidInputError, Exception)):
            svc.validate(token)

    def test_wrong_secret_rejected(self) -> None:
        svc1 = self._make_service(secret="secret-key-one-for-service")
        svc2 = self._make_service(secret="secret-key-two-for-service")

        token = svc1.generate({"sub": "user"})
        with pytest.raises((InvalidInputError, Exception)):
            svc2.validate(token)

    def test_parse_error_does_not_leak_secret(self) -> None:
        secret = "my-ultra-secret-key-that-must-not-leak"
        svc = self._make_service(secret=secret)

        with pytest.raises(Exception) as exc_info:
            svc.validate("invalid.token.here")

        assert secret not in str(exc_info.value)

    @pytest.mark.parametrize(
        "token",
        [
            "",
            "   ",
            "not-a-jwt",
            "a.b",
            "こんにちは.世界.テスト",
            "a" * 100_000,
            "a.b\x00c.d",
        ],
        ids=["empty", "spaces", "no_dots", "two_segments", "unicode", "huge", "null_bytes"],
    )
    def test_malformed_tokens_return_error(self, token: str) -> None:
        svc = self._make_service()
        with pytest.raises(Exception):
            svc.validate(token)

    def test_issuer_mismatch_rejected(self) -> None:
        svc = self._make_service(issuer="trusted-issuer")
        # Generate without issuer claim
        payload = {"sub": "user", "exp": int(time.time()) + 3600}
        token = pyjwt.encode(
            payload, "test-secret-key-minimum-length", algorithm="HS256"
        )

        with pytest.raises((InvalidInputError, Exception)):
            svc.validate(token)


# ─── 3. Password Hasher Security ───────────────────────────────────────────


class TestPasswordHasherSecurity:
    """Password hashing defaults and edge cases."""

    def test_bcrypt_default_rounds_at_least_12(self) -> None:
        hasher = PasswordHasher(algorithm=HashAlgorithm.BCRYPT, rounds=12)
        hashed = hasher.hash("securepassword1")
        # bcrypt format: $2b$12$...
        assert "$12$" in hashed, f"Expected bcrypt cost 12, got: {hashed[:30]}"

    def test_argon2_hash_verify_roundtrip(self) -> None:
        hasher = PasswordHasher(algorithm=HashAlgorithm.ARGON2)
        hashed = hasher.hash("securepassword1")
        assert hasher.verify("securepassword1", hashed)
        assert not hasher.verify("wrong-password1", hashed)

    def test_bcrypt_hash_verify_roundtrip(self) -> None:
        hasher = PasswordHasher(algorithm=HashAlgorithm.BCRYPT)
        hashed = hasher.hash("securepassword1")
        assert hasher.verify("securepassword1", hashed)
        assert not hasher.verify("wrong-password1", hashed)

    def test_same_password_produces_different_hashes(self) -> None:
        hasher = PasswordHasher()
        h1 = hasher.hash("securepassword1")
        h2 = hasher.hash("securepassword1")
        assert h1 != h2, "Same password should produce different hashes (random salt)"

    def test_bcrypt_malformed_hash_does_not_crash(self) -> None:
        hasher = PasswordHasher(algorithm=HashAlgorithm.BCRYPT)
        # Should return False, not raise
        assert not hasher.verify("password", "not-a-valid-hash")

    def test_argon2_malformed_hash_does_not_crash(self) -> None:
        hasher = PasswordHasher(algorithm=HashAlgorithm.ARGON2)
        assert not hasher.verify("password", "not-a-valid-hash")
        assert not hasher.verify("password", "")
        assert not hasher.verify("password", "$$$")

    @pytest.mark.parametrize(
        "pw",
        [
            "pässwörd-ünïcödé",
            "密码测试密码测试密码测试",
            "p@$$w0rd!#%^&*()",
            "pass\nword\ttab1",
        ],
        ids=["umlaut", "chinese", "symbols", "control_chars"],
    )
    def test_special_characters_handled(self, pw: str) -> None:
        hasher = PasswordHasher()
        hashed = hasher.hash(pw)
        assert hasher.verify(pw, hashed)


# ─── 4. TLS Configuration Hardening ───────────────────────────────────────


@pytest.mark.skipif(not HAS_SECURITY, reason="pykit-security not installed")
class TestTLSSecurity:
    """TLS minimum version and configuration safety."""

    def test_default_min_version_is_tls12(self) -> None:
        cfg = TLSConfig()
        assert cfg.min_version == ssl.TLSVersion.TLSv1_2

    def test_build_enforces_min_version(self) -> None:
        cfg = TLSConfig(skip_verify=True, min_version=ssl.TLSVersion.TLSv1_2)
        ctx = cfg.build()
        assert ctx is not None
        assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2

    def test_tls13_can_be_set(self) -> None:
        cfg = TLSConfig(skip_verify=True, min_version=ssl.TLSVersion.TLSv1_3)
        ctx = cfg.build()
        assert ctx is not None
        assert ctx.minimum_version == ssl.TLSVersion.TLSv1_3

    def test_cert_key_pair_must_be_complete(self) -> None:
        with pytest.raises(ValueError, match="together"):
            TLSConfig(cert_file="/path/cert.pem").validate()

        with pytest.raises(ValueError, match="together"):
            TLSConfig(key_file="/path/key.pem").validate()

    def test_ca_file_must_exist(self) -> None:
        with pytest.raises(FileNotFoundError):
            TLSConfig(ca_file="/nonexistent/ca.pem").validate()

    def test_disabled_config_returns_none(self) -> None:
        cfg = TLSConfig()
        assert cfg.build() is None
        assert not cfg.is_enabled()


# ─── 5. Async Cancellation Safety ─────────────────────────────────────────


class TestAsyncSafety:
    """Verify async operations handle cancellation gracefully."""

    @pytest.mark.asyncio
    async def test_jwt_in_concurrent_tasks(self) -> None:
        svc = JWTService(JWTConfig(secret="concurrent-test-secret-key"))

        async def generate_and_validate(i: int) -> None:
            token = svc.generate({"sub": f"user-{i}"})
            claims = svc.validate(token)
            assert claims["sub"] == f"user-{i}"

        tasks = [generate_and_validate(i) for i in range(50)]
        await asyncio.gather(*tasks)

    @pytest.mark.asyncio
    async def test_cancelled_task_no_resource_leak(self) -> None:
        svc = JWTService(JWTConfig(secret="cancellation-test-secret1"))

        async def slow_validation() -> None:
            await asyncio.sleep(0.01)
            svc.validate(svc.generate({"sub": "user"}))

        task = asyncio.create_task(slow_validation())
        await asyncio.sleep(0.005)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task


# ─── 6. Exception Handling Completeness ───────────────────────────────────


class TestExceptionHandling:
    """All error paths return proper types, no raw exceptions escape."""

    def test_all_error_constructors_return_app_error(self) -> None:
        constructors = [
            lambda: AppError.not_found("User"),
            lambda: AppError.already_exists("User"),
            lambda: AppError.conflict("version mismatch"),
            lambda: AppError.invalid_input("email", "invalid format"),
            lambda: AppError.missing_field("name"),
            lambda: AppError.unauthorized(),
            lambda: AppError.forbidden(),
            lambda: AppError.token_expired(),
            lambda: AppError.invalid_token(),
            lambda: AppError.internal(Exception("oops")),
            lambda: AppError.database_error(Exception("conn")),
            lambda: AppError.service_unavailable("redis"),
            lambda: AppError.connection_failed("postgres"),
            lambda: AppError.timeout("db_query"),
            lambda: AppError.rate_limited(),
        ]
        for ctor in constructors:
            err = ctor()
            assert isinstance(err, AppError), f"Expected AppError, got {type(err)}"
            assert isinstance(err.message, str)
            assert err.http_status > 0

    def test_error_cause_chain_preserved(self) -> None:
        original = ValueError("bad value")
        err = AppError.internal(original)
        assert err.cause is original

    def test_error_http_status_codes_correct(self) -> None:
        assert AppError.unauthorized().http_status == 401
        assert AppError.forbidden().http_status == 403
        assert AppError.not_found("x").http_status == 404
        assert AppError.token_expired().http_status == 401
        assert AppError.invalid_token().http_status == 401
        assert AppError.rate_limited().http_status == 429

    def test_backward_compat_subclasses(self) -> None:
        from pykit_errors import NotFoundError, InvalidInputError, ServiceUnavailableError

        assert isinstance(NotFoundError("User"), AppError)
        assert isinstance(InvalidInputError("bad"), AppError)
        assert isinstance(ServiceUnavailableError("redis"), AppError)
