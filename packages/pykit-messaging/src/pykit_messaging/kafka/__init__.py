"""Kafka provider for pykit-messaging."""

from __future__ import annotations

from dataclasses import fields

from pykit_messaging.config import BrokerConfig
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
from pykit_messaging.registry import MessagingRegistry


def register(registry: MessagingRegistry) -> None:
    """Register Kafka producer and consumer factories."""
    registry.register_producer("kafka", lambda config: KafkaProducer(_config_from(config)))
    registry.register_consumer("kafka", lambda config: KafkaConsumer(_config_from(config)))


def _config_from(config: BrokerConfig) -> KafkaConfig:
    if isinstance(config, KafkaConfig):
        config.validate()
        return config
    allowed = {field.name for field in fields(KafkaConfig)}
    return KafkaConfig(**{key: value for key, value in config.__dict__.items() if key in allowed})


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
    "register",
    "is_connection_error",
    "is_retryable_error",
]
