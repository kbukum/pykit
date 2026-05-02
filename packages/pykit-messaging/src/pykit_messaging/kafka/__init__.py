"""Kafka provider for pykit-messaging."""

from __future__ import annotations

from pykit_messaging.kafka.component import KafkaComponent
from pykit_messaging.kafka.config import KafkaConfig
from pykit_messaging.kafka.consumer import KafkaConsumer
from pykit_messaging.kafka.errors import KafkaErrorClassifier, is_connection_error, is_retryable_error
from pykit_messaging.kafka.middleware import (
    DeadLetterEnvelope,
    DeadLetterProducer,
    InstrumentHandler,
    RetryHandler,
    RetryMiddlewareConfig,
    TracingHandler,
)
from pykit_messaging.kafka.producer import KafkaProducer

__all__ = [
    "DeadLetterEnvelope",
    "DeadLetterProducer",
    "InstrumentHandler",
    "KafkaComponent",
    "KafkaConfig",
    "KafkaConsumer",
    "KafkaErrorClassifier",
    "KafkaProducer",
    "RetryHandler",
    "RetryMiddlewareConfig",
    "TracingHandler",
    "is_connection_error",
    "is_retryable_error",
]
