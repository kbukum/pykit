"""Messaging middleware — reusable handler wrappers for cross-cutting concerns."""

from __future__ import annotations

from pykit_messaging.middleware.circuit_breaker import (
    CircuitBreakerConfig,
    CircuitBreakerHandler,
    circuit_breaker,
)
from pykit_messaging.middleware.dead_letter import DeadLetterConfig, DeadLetterEnvelope, DeadLetterProducer
from pykit_messaging.middleware.dedup import DedupConfig, DedupHandler, dedup
from pykit_messaging.middleware.metrics import MetricsHandler, instrument
from pykit_messaging.middleware.retry import RetryConfig, RetryHandler, retry
from pykit_messaging.middleware.stack import StackBuilder

__all__ = [
    "CircuitBreakerConfig",
    "CircuitBreakerHandler",
    "DeadLetterConfig",
    "DeadLetterEnvelope",
    "DeadLetterProducer",
    "DedupConfig",
    "DedupHandler",
    "MetricsHandler",
    "RetryConfig",
    "RetryHandler",
    "StackBuilder",
    "circuit_breaker",
    "dedup",
    "instrument",
    "retry",
]
