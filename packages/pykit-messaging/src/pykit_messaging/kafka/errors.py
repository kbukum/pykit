"""Kafka-specific error classification built on the abstract error layer."""

from __future__ import annotations

from pykit_messaging.errors import (
    is_connection_error as _generic_is_connection_error,
)
from pykit_messaging.errors import (
    is_retryable_error as _generic_is_retryable_error,
)

# Kafka-specific patterns that extend the generic ones.
KAFKA_CONNECTION_PATTERNS: tuple[str, ...] = (
    "broker not available",
    "leader not available",
)

KAFKA_RETRYABLE_PATTERNS: tuple[str, ...] = (
    "not enough replicas",
    "offset out of range",
)


def is_connection_error(err: BaseException | None) -> bool:
    """Return ``True`` if *err* looks like a Kafka connection error."""
    return _generic_is_connection_error(err, extra_patterns=KAFKA_CONNECTION_PATTERNS)


def is_retryable_error(err: BaseException | None) -> bool:
    """Return ``True`` if *err* is retryable (connection or transient)."""
    return _generic_is_retryable_error(
        err,
        extra_connection_patterns=KAFKA_CONNECTION_PATTERNS,
        extra_retryable_patterns=KAFKA_RETRYABLE_PATTERNS,
    )


class KafkaErrorClassifier:
    """Implements :class:`~pykit_messaging.errors.ErrorClassifier` for Kafka."""

    def is_connection_error(self, error: Exception) -> bool:
        return is_connection_error(error)

    def is_retryable_error(self, error: Exception) -> bool:
        return is_retryable_error(error)
