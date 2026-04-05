"""Broker-agnostic error classification for retry and circuit-breaker decisions."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

# Generic connection error patterns shared across broker implementations.
GENERIC_CONNECTION_PATTERNS: tuple[str, ...] = (
    "connection refused",
    "connection reset",
    "broken pipe",
    "i/o timeout",
    "no route to host",
    "network is unreachable",
    "connection closed",
    "dial tcp",
    "network exception",
)

# Generic retryable error patterns (transient failures).
GENERIC_RETRYABLE_PATTERNS: tuple[str, ...] = (
    "temporary",
    "request timed out",
)


@runtime_checkable
class ErrorClassifier(Protocol):
    """Classifies errors for retry/circuit-breaker decisions."""

    def is_connection_error(self, error: Exception) -> bool: ...

    def is_retryable_error(self, error: Exception) -> bool: ...


def is_connection_error(
    err: BaseException | None,
    *,
    extra_patterns: tuple[str, ...] = (),
) -> bool:
    """Return ``True`` if *err* looks like a connection error.

    Checks against :data:`GENERIC_CONNECTION_PATTERNS` plus any
    broker-specific *extra_patterns*.
    """
    if err is None:
        return False
    msg = str(err).lower()
    patterns = GENERIC_CONNECTION_PATTERNS + extra_patterns
    return any(p in msg for p in patterns)


def is_retryable_error(
    err: BaseException | None,
    *,
    extra_connection_patterns: tuple[str, ...] = (),
    extra_retryable_patterns: tuple[str, ...] = (),
) -> bool:
    """Return ``True`` if *err* is retryable (connection or transient).

    Checks connection patterns first, then generic + broker-specific
    retryable patterns.
    """
    if err is None:
        return False
    if is_connection_error(err, extra_patterns=extra_connection_patterns):
        return True
    msg = str(err).lower()
    patterns = GENERIC_RETRYABLE_PATTERNS + extra_retryable_patterns
    return any(p in msg for p in patterns)
