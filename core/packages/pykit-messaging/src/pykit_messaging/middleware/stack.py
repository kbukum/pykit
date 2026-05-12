"""Middleware stack builder for composing handler pipelines."""

from __future__ import annotations

from collections.abc import Callable

from pykit_messaging.handler import MessageHandlerProtocol, chain_handlers
from pykit_messaging.metrics import MetricsCollector
from pykit_messaging.middleware.circuit_breaker import CircuitBreakerConfig, circuit_breaker
from pykit_messaging.middleware.dedup import DedupConfig, dedup
from pykit_messaging.middleware.metrics import instrument
from pykit_messaging.middleware.retry import RetryConfig, retry


class StackBuilder:
    """Fluent builder for composing messaging middleware.

    Middleware is applied in a fixed order regardless of builder call order:

    ``Metrics → Dedup → CircuitBreaker → Retry → Handler``

    This order ensures metrics are collected for all operations, deduplication
    happens before circuit breaking, and retries are applied before the base handler.

    Example::

        handler = (
            StackBuilder(base_handler)
            .with_retry(RetryConfig(max_attempts=3))
            .with_metrics(collector, "my-topic")
            .build()
        )
    """

    def __init__(self, base: MessageHandlerProtocol) -> None:
        """Initialize the stack builder with a base handler.

        Args:
            base: The innermost handler to wrap with middleware.
        """
        self._base = base
        self._retry_cfg: RetryConfig | None = None
        self._metrics: tuple[MetricsCollector, str] | None = None
        self._dedup_cfg: DedupConfig | None = None
        self._cb_cfg: CircuitBreakerConfig | None = None

    def with_retry(self, config: RetryConfig | None = None) -> StackBuilder:
        """Add retry middleware with exponential backoff.

        Args:
            config: Optional retry configuration; defaults to ``RetryConfig()``.

        Returns:
            Self for method chaining.
        """
        self._retry_cfg = config or RetryConfig()
        return self

    def with_metrics(self, collector: MetricsCollector, topic: str) -> StackBuilder:
        """Add metrics/instrumentation middleware.

        Args:
            collector: The metrics collector to record metrics to.
            topic: The topic being consumed from.

        Returns:
            Self for method chaining.
        """
        self._metrics = (collector, topic)
        return self

    def with_dedup(self, config: DedupConfig | None = None) -> StackBuilder:
        """Add deduplication middleware.

        Args:
            config: Optional dedup configuration; defaults to ``DedupConfig()``.

        Returns:
            Self for method chaining.
        """
        self._dedup_cfg = config or DedupConfig()
        return self

    def with_circuit_breaker(self, config: CircuitBreakerConfig | None = None) -> StackBuilder:
        """Add circuit breaker middleware.

        Args:
            config: Optional circuit breaker configuration; defaults to ``CircuitBreakerConfig()``.

        Returns:
            Self for method chaining.
        """
        self._cb_cfg = config or CircuitBreakerConfig()
        return self

    def build(self) -> MessageHandlerProtocol:
        """Build the fully-wrapped handler.

        Middleware is applied in the following order (inner → outer):

        1. Retry (innermost, closest to handler)
        2. Circuit breaker
        3. Dedup
        4. Metrics (outermost)

        Returns:
            The fully wrapped handler ready for message processing.
        """
        middlewares: list[Callable[[MessageHandlerProtocol], MessageHandlerProtocol]] = []

        if self._retry_cfg is not None:
            middlewares.append(retry(self._retry_cfg))
        if self._cb_cfg is not None:
            middlewares.append(circuit_breaker(self._cb_cfg))
        if self._dedup_cfg is not None:
            middlewares.append(dedup(self._dedup_cfg))
        if self._metrics is not None:
            collector, topic = self._metrics
            middlewares.append(instrument(collector, topic))

        return chain_handlers(self._base, *middlewares)
