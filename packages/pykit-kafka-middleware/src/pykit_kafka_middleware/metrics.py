"""Prometheus metrics middleware for message handlers."""

from __future__ import annotations

import time

from prometheus_client import Counter, Histogram

from pykit_messaging.types import Message, MessageHandler

# Module-level metrics — created once, shared across all InstrumentHandler calls.
_messages_total = Counter(
    "kafka_consumer_messages_total",
    "Total number of consumed messages",
    ["topic", "group"],
)
_errors_total = Counter(
    "kafka_consumer_errors_total",
    "Total number of consumer errors",
    ["topic", "group"],
)
_processing_duration = Histogram(
    "kafka_consumer_processing_duration_seconds",
    "Duration of message processing in seconds",
    ["topic", "group"],
)


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

    if metric_prefix == "kafka_consumer":
        msgs = _messages_total
        errs = _errors_total
        dur = _processing_duration
    else:
        msgs = Counter(
            f"{metric_prefix}_messages_total",
            "Total number of consumed messages",
            ["topic", "group"],
        )
        errs = Counter(
            f"{metric_prefix}_errors_total",
            "Total number of consumer errors",
            ["topic", "group"],
        )
        dur = Histogram(
            f"{metric_prefix}_processing_duration_seconds",
            "Duration of message processing in seconds",
            ["topic", "group"],
        )

    async def wrapper(msg: Message) -> None:
        start = time.monotonic()
        try:
            await handler(msg)
        except Exception:
            errs.labels(topic=topic, group=group).inc()
            raise
        finally:
            duration = time.monotonic() - start
            msgs.labels(topic=topic, group=group).inc()
            dur.labels(topic=topic, group=group).observe(duration)

    return wrapper
