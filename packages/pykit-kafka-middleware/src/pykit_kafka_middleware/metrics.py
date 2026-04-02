"""Prometheus metrics middleware for Kafka message handlers."""

from __future__ import annotations

import time

from prometheus_client import Counter, Histogram

from pykit_kafka.types import Message, MessageHandler


def InstrumentHandler(
    topic: str,
    group: str,
    handler: MessageHandler,
) -> MessageHandler:
    """Wrap a MessageHandler with Prometheus metrics instrumentation.

    Metrics recorded:

    - ``kafka_consumer_messages_total``  — counter of messages processed
    - ``kafka_consumer_errors_total``    — counter of processing errors
    - ``kafka_consumer_processing_duration_seconds`` — processing latency histogram
    """
    messages_total = Counter(
        "kafka_consumer_messages_total",
        "Total number of consumed Kafka messages",
        ["topic", "group"],
    )
    errors_total = Counter(
        "kafka_consumer_errors_total",
        "Total number of Kafka consumer errors",
        ["topic", "group"],
    )
    processing_duration = Histogram(
        "kafka_consumer_processing_duration_seconds",
        "Duration of Kafka message processing in seconds",
        ["topic", "group"],
    )

    async def wrapper(msg: Message) -> None:
        start = time.monotonic()
        try:
            await handler(msg)
        except Exception:
            errors_total.labels(topic=topic, group=group).inc()
            raise
        finally:
            duration = time.monotonic() - start
            messages_total.labels(topic=topic, group=group).inc()
            processing_duration.labels(topic=topic, group=group).observe(duration)

    return wrapper
