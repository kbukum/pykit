"""Prometheus metrics middleware for message handlers."""

from __future__ import annotations

import time

from pykit_messaging.types import Message, MessageHandler
from pykit_observability import MessageMetrics

# Module-level metrics — created once, shared across all InstrumentHandler calls.
_default_metrics = MessageMetrics()


def InstrumentHandler(
    topic: str,
    group: str,
    handler: MessageHandler,
    *,
    metric_prefix: str = "kafka_consumer",
) -> MessageHandler:
    """Wrap a MessageHandler with Prometheus metrics instrumentation.

    By default metrics use the ``kafka_consumer`` prefix for backward
    compatibility.  Pass *metric_prefix* to use a different prefix when
    the handler is backed by a non-Kafka broker.

    When using the default prefix the pre-registered module-level metrics are
    reused.  A custom prefix dynamically creates dedicated counters/histogram.

    Metrics recorded (shown with default prefix):

    - ``kafka_consumer_messages_total``  — counter of messages processed
    - ``kafka_consumer_errors_total``    — counter of processing errors
    - ``kafka_consumer_processing_duration_seconds`` — processing latency histogram
    """

    metrics = _default_metrics if metric_prefix == "kafka_consumer" else MessageMetrics(metric_prefix)

    async def wrapper(msg: Message) -> None:
        start = time.monotonic()
        errored = False
        try:
            await handler(msg)
        except Exception:
            errored = True
            raise
        finally:
            duration = time.monotonic() - start
            metrics.record(topic, group, duration, error=errored)

    return wrapper
