"""Tests for pykit_logging.masking."""

from __future__ import annotations

import io
import json
import sys
from typing import Any

import structlog

from pykit_logging.masking import DefaultMasker, MaskingConfig, masking_processor
from pykit_logging.setup import setup_logging


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event_dict(**kwargs: Any) -> dict[str, Any]:
    """Build a minimal structlog event_dict for processor tests."""
    return kwargs


# ---------------------------------------------------------------------------
# Field-name masking
# ---------------------------------------------------------------------------

class TestFieldNameMasking:
    """Ensure that values for known sensitive field names are fully replaced."""

    def test_password(self) -> None:
        m = DefaultMasker()
        assert m.mask_value("password", "hunter2") == "***REDACTED***"

    def test_token(self) -> None:
        m = DefaultMasker()
        assert m.mask_value("token", "abc123") == "***REDACTED***"

    def test_api_key(self) -> None:
        m = DefaultMasker()
        assert m.mask_value("api_key", "sk-abc123") == "***REDACTED***"

    def test_apikey(self) -> None:
        m = DefaultMasker()
        assert m.mask_value("apikey", "sk-abc123") == "***REDACTED***"

    def test_api_dash_key(self) -> None:
        m = DefaultMasker()
        assert m.mask_value("api-key", "sk-abc123") == "***REDACTED***"

    def test_authorization(self) -> None:
        m = DefaultMasker()
        assert m.mask_value("authorization", "Bearer xyz") == "***REDACTED***"

    def test_auth_token(self) -> None:
        m = DefaultMasker()
        assert m.mask_value("auth_token", "tok") == "***REDACTED***"

    def test_access_token(self) -> None:
        m = DefaultMasker()
        assert m.mask_value("access_token", "tok") == "***REDACTED***"

    def test_refresh_token(self) -> None:
        m = DefaultMasker()
        assert m.mask_value("refresh_token", "tok") == "***REDACTED***"

    def test_private_key(self) -> None:
        m = DefaultMasker()
        assert m.mask_value("private_key", "-----BEGIN RSA KEY-----") == "***REDACTED***"

    def test_ssn_field(self) -> None:
        m = DefaultMasker()
        assert m.mask_value("ssn", "123-45-6789") == "***REDACTED***"

    def test_credit_card_field(self) -> None:
        m = DefaultMasker()
        assert m.mask_value("credit_card", "4111111111111111") == "***REDACTED***"

    def test_card_number(self) -> None:
        m = DefaultMasker()
        assert m.mask_value("card_number", "4111111111111111") == "***REDACTED***"

    def test_cvv(self) -> None:
        m = DefaultMasker()
        assert m.mask_value("cvv", "123") == "***REDACTED***"

    def test_pin(self) -> None:
        m = DefaultMasker()
        assert m.mask_value("pin", "0000") == "***REDACTED***"

    def test_secret(self) -> None:
        m = DefaultMasker()
        assert m.mask_value("secret", "s3cr3t") == "***REDACTED***"


class TestFieldNameCaseInsensitivity:
    """Field-name matching must be case-insensitive."""

    def test_uppercase(self) -> None:
        m = DefaultMasker()
        assert m.mask_value("PASSWORD", "hunter2") == "***REDACTED***"

    def test_mixed_case(self) -> None:
        m = DefaultMasker()
        assert m.mask_value("Api_Key", "sk-abc") == "***REDACTED***"

    def test_title_case(self) -> None:
        m = DefaultMasker()
        assert m.mask_value("Authorization", "Bearer xyz") == "***REDACTED***"


# ---------------------------------------------------------------------------
# Value-pattern masking
# ---------------------------------------------------------------------------

class TestValuePatternMasking:
    """Regex-based value patterns applied regardless of key name."""

    def test_email(self) -> None:
        m = DefaultMasker()
        result = m.mask_value("user_info", "contact alice@example.com for details")
        assert "***@***.***" in result
        assert "alice@example.com" not in result

    def test_credit_card_preserves_last_four(self) -> None:
        m = DefaultMasker()
        result = m.mask_value("data", "card is 4111-1111-1111-1234")
        assert "1234" in result
        assert "4111-1111-1111-1234" not in result
        assert "****-****-****-1234" in result

    def test_credit_card_no_separator(self) -> None:
        m = DefaultMasker()
        result = m.mask_value("data", "num 4111111111115678")
        assert "5678" in result
        assert "4111111111115678" not in result

    def test_ssn_pattern(self) -> None:
        m = DefaultMasker()
        result = m.mask_value("info", "ssn: 123-45-6789")
        assert "***-**-****" in result
        assert "123-45-6789" not in result

    def test_ssn_no_dashes(self) -> None:
        m = DefaultMasker()
        result = m.mask_value("info", "ssn: 123456789")
        assert "***-**-****" in result

    def test_jwt(self) -> None:
        jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6Ikp"
            "vaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ."
            "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        m = DefaultMasker()
        result = m.mask_value("header", f"token {jwt}")
        assert "[JWT_REDACTED]" in result
        assert "eyJ" not in result

    def test_bearer_token(self) -> None:
        m = DefaultMasker()
        result = m.mask_value("header", "Bearer eyabc123.def456.ghi789")
        assert "Bearer [REDACTED]" in result

    def test_bearer_case_insensitive(self) -> None:
        m = DefaultMasker()
        result = m.mask_value("header", "bearer abc123token")
        assert "Bearer [REDACTED]" in result

    def test_aws_access_key(self) -> None:
        m = DefaultMasker()
        result = m.mask_value("config", "key=AKIAIOSFODNN7EXAMPLE")
        assert "[AWS_KEY_REDACTED]" in result
        assert "AKIAIOSFODNN7EXAMPLE" not in result

    def test_hex_secret(self) -> None:
        hex_val = "a" * 40  # 40-char hex — e.g. SHA-1
        m = DefaultMasker()
        result = m.mask_value("data", f"hash={hex_val}")
        assert "[HEX_REDACTED]" in result
        assert hex_val not in result


# ---------------------------------------------------------------------------
# Config: custom field names / patterns / disabled
# ---------------------------------------------------------------------------

class TestCustomConfig:
    def test_custom_field_names(self) -> None:
        cfg = MaskingConfig(field_names=("x_custom_secret",))
        m = DefaultMasker(cfg)
        assert m.mask_value("x_custom_secret", "val") == "***REDACTED***"
        # Default names still work
        assert m.mask_value("password", "pw") == "***REDACTED***"

    def test_custom_replacement(self) -> None:
        cfg = MaskingConfig(replacement="[HIDDEN]")
        m = DefaultMasker(cfg)
        assert m.mask_value("password", "pw") == "[HIDDEN]"

    def test_custom_value_pattern(self) -> None:
        cfg = MaskingConfig(value_patterns=(r"CUSTOM-\d{6}",))
        m = DefaultMasker(cfg)
        result = m.mask_value("ref", "id is CUSTOM-123456")
        assert "***REDACTED***" in result
        assert "CUSTOM-123456" not in result

    def test_disabled(self) -> None:
        cfg = MaskingConfig(enabled=False)
        m = DefaultMasker(cfg)
        assert m.mask_value("password", "hunter2") == "hunter2"
        assert m.mask_value("data", "alice@example.com") == "alice@example.com"


# ---------------------------------------------------------------------------
# Non-sensitive data passes through unchanged
# ---------------------------------------------------------------------------

class TestPassthrough:
    def test_plain_text(self) -> None:
        m = DefaultMasker()
        assert m.mask_value("message", "hello world") == "hello world"

    def test_numeric_string(self) -> None:
        m = DefaultMasker()
        assert m.mask_value("count", "42") == "42"

    def test_url_without_secrets(self) -> None:
        m = DefaultMasker()
        url = "https://example.com/api/v1/users"
        assert m.mask_value("url", url) == url


# ---------------------------------------------------------------------------
# masking_processor with structlog event_dict
# ---------------------------------------------------------------------------

class TestMaskingProcessor:
    def test_masks_sensitive_key(self) -> None:
        proc = masking_processor()
        ed = _make_event_dict(event="login attempt", password="secret123")
        result = proc(None, "info", ed)  # type: ignore[arg-type]
        assert result["password"] == "***REDACTED***"
        assert result["event"] == "login attempt"

    def test_masks_event_message(self) -> None:
        proc = masking_processor()
        ed = _make_event_dict(event="user alice@example.com logged in")
        result = proc(None, "info", ed)  # type: ignore[arg-type]
        assert "***@***.***" in result["event"]
        assert "alice@example.com" not in result["event"]

    def test_non_string_value_with_sensitive_content(self) -> None:
        """Non-string values are stringified and checked."""
        proc = masking_processor()
        ed = _make_event_dict(event="data", payload={"email": "alice@example.com"})
        result = proc(None, "info", ed)  # type: ignore[arg-type]
        payload = result["payload"]
        # The dict is converted to str, email is masked
        assert "alice@example.com" not in str(payload)

    def test_leaves_non_sensitive_unchanged(self) -> None:
        proc = masking_processor()
        ed = _make_event_dict(event="ok", user="bob", count=42)
        result = proc(None, "info", ed)  # type: ignore[arg-type]
        assert result["user"] == "bob"
        assert result["count"] == 42

    def test_custom_masker(self) -> None:
        cfg = MaskingConfig(enabled=False)
        proc = masking_processor(masker=DefaultMasker(cfg))
        ed = _make_event_dict(event="test", password="secret")
        result = proc(None, "info", ed)  # type: ignore[arg-type]
        assert result["password"] == "secret"


# ---------------------------------------------------------------------------
# Full pipeline: setup_logging → log → verify masking
# ---------------------------------------------------------------------------

class TestFullPipeline:
    def test_json_output_masks_password(self) -> None:
        """setup_logging with JSON format should produce masked output."""
        buf = io.StringIO()
        setup_logging(level="DEBUG", log_format="json", service_name="test-mask")

        # Reconfigure structlog to write to our buffer instead of stderr
        processors = list(structlog.get_config()["processors"])
        structlog.configure(
            processors=processors,
            wrapper_class=structlog.get_config()["wrapper_class"],
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=buf),
            cache_logger_on_first_use=False,
        )

        logger = structlog.get_logger("mask-test")
        logger.info("user login", password="supersecret")

        output = buf.getvalue()
        assert "supersecret" not in output
        assert "***REDACTED***" in output

    def test_masking_disabled_passes_through(self) -> None:
        """With masking disabled, sensitive values appear in output."""
        buf = io.StringIO()
        cfg = MaskingConfig(enabled=False)
        setup_logging(level="DEBUG", log_format="json", service_name="test-nomask", masking=cfg)

        processors = list(structlog.get_config()["processors"])
        structlog.configure(
            processors=processors,
            wrapper_class=structlog.get_config()["wrapper_class"],
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=buf),
            cache_logger_on_first_use=False,
        )

        logger = structlog.get_logger("mask-test")
        logger.info("user login", password="supersecret")

        output = buf.getvalue()
        assert "supersecret" in output

    def test_email_masked_in_event_message(self) -> None:
        """Emails embedded in log messages are masked."""
        buf = io.StringIO()
        setup_logging(level="DEBUG", log_format="json", service_name="test-email")

        processors = list(structlog.get_config()["processors"])
        structlog.configure(
            processors=processors,
            wrapper_class=structlog.get_config()["wrapper_class"],
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=buf),
            cache_logger_on_first_use=False,
        )

        logger = structlog.get_logger("mask-test")
        logger.info("sent to alice@example.com")

        output = buf.getvalue()
        assert "alice@example.com" not in output
        assert "***@***.***" in output
