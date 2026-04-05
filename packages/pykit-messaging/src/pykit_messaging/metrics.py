"""Messaging metrics collection protocols and implementations."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class MetricsCollector(Protocol):
    """Collects messaging operational metrics."""

    def record_publish(self, topic: str, duration_ms: float, *, success: bool) -> None:
        """Record a publish operation metric.

        Args:
            topic: The topic the message was published to.
            duration_ms: Duration of the publish in milliseconds.
            success: Whether the publish succeeded.
        """
        ...

    def record_consume(self, topic: str, duration_ms: float, *, success: bool) -> None:
        """Record a consume operation metric.

        Args:
            topic: The topic the message was consumed from.
            duration_ms: Duration of the consume handler in milliseconds.
            success: Whether the consume handler succeeded.
        """
        ...


class NoopMetrics:
    """No-op metrics collector for when metrics are disabled."""

    def record_publish(self, topic: str, duration_ms: float, *, success: bool) -> None:
        """No-op publish metric."""

    def record_consume(self, topic: str, duration_ms: float, *, success: bool) -> None:
        """No-op consume metric."""
