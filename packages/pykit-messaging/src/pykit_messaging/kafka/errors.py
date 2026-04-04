"""Error classification helpers for Kafka errors."""

from __future__ import annotations

_CONNECTION_PATTERNS = (
    "connection refused",
    "connection reset",
    "broken pipe",
    "i/o timeout",
    "no route to host",
    "network is unreachable",
    "broker not available",
    "leader not available",
    "connection closed",
    "dial tcp",
    "network exception",
)

_RETRYABLE_PATTERNS = (
    "temporary",
    "request timed out",
    "not enough replicas",
    "offset out of range",
)


def is_connection_error(err: BaseException | None) -> bool:
    """Return ``True`` if *err* looks like a Kafka connection error."""
    if err is None:
        return False
    msg = str(err).lower()
    return any(p in msg for p in _CONNECTION_PATTERNS)


def is_retryable_error(err: BaseException | None) -> bool:
    """Return ``True`` if *err* is retryable (connection or transient)."""
    if err is None:
        return False
    if is_connection_error(err):
        return True
    msg = str(err).lower()
    return any(p in msg for p in _RETRYABLE_PATTERNS)
