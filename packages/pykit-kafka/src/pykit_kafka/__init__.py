"""pykit-kafka — Kafka producer/consumer built on aiokafka."""

from __future__ import annotations

from pykit_kafka.component import KafkaComponent
from pykit_kafka.config import KafkaConfig
from pykit_kafka.consumer import KafkaConsumer
from pykit_kafka.errors import is_connection_error, is_retryable_error
from pykit_kafka.producer import KafkaProducer
from pykit_kafka.types import Event, EventHandler, Message, MessageHandler

__all__ = [
    "Event",
    "EventHandler",
    "KafkaComponent",
    "KafkaConfig",
    "KafkaConsumer",
    "KafkaProducer",
    "Message",
    "MessageHandler",
    "is_connection_error",
    "is_retryable_error",
]
