"""Messaging middleware — reusable handler wrappers for cross-cutting concerns."""

from __future__ import annotations

from pykit_messaging.middleware.circuit_breaker import (
    CircuitBreakerConfig,
    CircuitBreakerHandler,
    circuit_breaker,
)
from pykit_messaging.middleware.dedup import DedupConfig, DedupHandler, dedup

__all__ = [
    "CircuitBreakerConfig",
    "CircuitBreakerHandler",
    "DedupConfig",
    "DedupHandler",
    "circuit_breaker",
    "dedup",
]
