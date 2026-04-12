"""Sensitive data masking for structured logging."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

import structlog


class Masker(Protocol):
    """Protocol for masking sensitive values in log output."""

    def mask_value(self, key: str, value: str) -> str:
        """Mask a value based on its field key and content.

        Args:
            key: The field name/key.
            value: The string value to potentially mask.

        Returns:
            The original value if no masking needed, or a masked version.
        """
        ...


_DEFAULT_FIELD_NAMES: frozenset[str] = frozenset({
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "api-key",
    "authorization",
    "auth_token",
    "access_token",
    "refresh_token",
    "private_key",
    "ssn",
    "credit_card",
    "card_number",
    "cvv",
    "pin",
})


def _mask_credit_card(match: re.Match[str]) -> str:
    """Replace credit card digits keeping only last 4."""
    digits = re.sub(r"[\s-]", "", match.group(0))
    return f"****-****-****-{digits[-4:]}"


_DEFAULT_VALUE_PATTERNS: tuple[tuple[re.Pattern[str], str | Any], ...] = (
    # JWT — must come before generic hex to avoid partial matches
    (
        re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]+"),
        "[JWT_REDACTED]",
    ),
    # Bearer token
    (
        re.compile(r"(?i)Bearer\s+[a-zA-Z0-9._~+/=-]+"),
        "Bearer [REDACTED]",
    ),
    # AWS access key
    (
        re.compile(r"AKIA[0-9A-Z]{16}"),
        "[AWS_KEY_REDACTED]",
    ),
    # Credit card (callable replacement to preserve last 4)
    (
        re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
        _mask_credit_card,
    ),
    # SSN
    (
        re.compile(r"\b\d{3}-?\d{2}-?\d{4}\b"),
        "***-**-****",
    ),
    # Email
    (
        re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
        "***@***.***",
    ),
    # Generic hex secret (32+ chars)
    (
        re.compile(r"\b[0-9a-fA-F]{32,}\b"),
        "[HEX_REDACTED]",
    ),
)


@dataclass(frozen=True)
class MaskingConfig:
    """Configuration for sensitive data masking.

    Attributes:
        enabled: Whether masking is active.
        field_names: Additional field names to mask (merged with defaults).
        value_patterns: Additional regex patterns to match against values.
        replacement: The string used when a field name matches a sensitive key.
    """

    enabled: bool = True
    field_names: tuple[str, ...] = ()
    value_patterns: tuple[str, ...] = ()
    replacement: str = "***REDACTED***"


class DefaultMasker:
    """Production-ready masker with common patterns for PII and secrets.

    Thread-safe: all mutable state is set during ``__init__`` and never
    modified afterwards.
    """

    def __init__(self, config: MaskingConfig | None = None) -> None:
        self._config = config or MaskingConfig()
        self._field_names: frozenset[str] = _DEFAULT_FIELD_NAMES | frozenset(
            n.lower() for n in self._config.field_names
        )
        # Build the pattern list: defaults + user-supplied patterns
        extra: list[tuple[re.Pattern[str], str]] = [
            (re.compile(p), self._config.replacement) for p in self._config.value_patterns
        ]
        self._value_patterns: tuple[tuple[re.Pattern[str], str | Any], ...] = (
            *_DEFAULT_VALUE_PATTERNS,
            *extra,
        )

    def mask_value(self, key: str, value: str) -> str:
        """Mask a value based on its field key and content.

        If the *key* (case-insensitive) matches a known sensitive field name the
        entire value is replaced with the configured replacement string.
        Otherwise each registered regex pattern is applied in order.

        Args:
            key: The field name/key.
            value: The string value to potentially mask.

        Returns:
            The original value if no masking needed, or a masked version.
        """
        if not self._config.enabled:
            return value

        if key.lower() in self._field_names:
            return self._config.replacement

        result = value
        for pattern, replacement in self._value_patterns:
            if callable(replacement) and not isinstance(replacement, str):
                result = pattern.sub(replacement, result)
            else:
                result = pattern.sub(replacement, result)
        return result


def masking_processor(
    masker: Masker | None = None,
) -> structlog.types.Processor:
    """Create a structlog processor that masks sensitive data in all fields.

    Args:
        masker: Masker instance to use. Defaults to ``DefaultMasker()``.

    Returns:
        A structlog processor function.
    """
    _masker: Masker = masker or DefaultMasker()

    def _processor(
        logger: Any,
        method_name: str,
        event_dict: dict[str, Any],
    ) -> dict[str, Any]:
        for key in list(event_dict.keys()):
            value = event_dict[key]
            if isinstance(value, str):
                event_dict[key] = _masker.mask_value(key, value)
            else:
                str_value = str(value)
                masked = _masker.mask_value(key, str_value)
                if masked != str_value:
                    event_dict[key] = masked
        return event_dict

    return _processor  # type: ignore[return-value]
