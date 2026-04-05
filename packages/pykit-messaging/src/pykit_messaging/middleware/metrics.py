"""Metrics middleware for message handlers."""

from __future__ import annotations

import time
from collections.abc import Callable

from pykit_messaging.handler import MessageHandlerProtocol
from pykit_messaging.metrics import MetricsCollector
from pykit_messaging.types import Message


class MetricsHandler:
    """Records consume duration and success/failure metrics.

    Args:
        inner: The handler to delegate to.
        collector: The metrics collector to record metrics to.
        topic: The topic being consumed from.
    """

    def __init__(
        self,
        inner: MessageHandlerProtocol,
        collector: MetricsCollector,
        topic: str,
    ) -> None:
        self._inner = inner
        self._collector = collector
        self._topic = topic

    async def handle(self, msg: Message) -> None:
        """Handle a message and record consume metrics.

        Args:
            msg: The message to handle.

        Raises:
            Any exception raised by the inner handler.
        """
        start = time.monotonic()
        success = True
        try:
            await self._inner.handle(msg)
        except Exception:
            success = False
            raise
        finally:
            duration_ms = (time.monotonic() - start) * 1000
            self._collector.record_consume(self._topic, duration_ms, success=success)


def instrument(
    collector: MetricsCollector,
    topic: str,
) -> Callable[[MessageHandlerProtocol], MessageHandlerProtocol]:
    """Return a middleware function for metrics instrumentation.

    Args:
        collector: The metrics collector to record metrics to.
        topic: The topic being consumed from.

    Returns:
        A middleware function compatible with ``chain_handlers``.
    """

    def _middleware(handler: MessageHandlerProtocol) -> MessageHandlerProtocol:
        return MetricsHandler(handler, collector, topic)

    return _middleware
