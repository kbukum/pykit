"""Kafka dead-letter queue producer for failed messages.

Kafka uses the canonical broker-agnostic DLQ envelope and redaction policy from
``pykit_messaging.middleware.dead_letter``.
"""

from __future__ import annotations

from pykit_messaging.middleware.dead_letter import (
    DeadLetterConfig,
    DeadLetterEnvelope,
)
from pykit_messaging.middleware.dead_letter import (
    DeadLetterProducer as _CoreDeadLetterProducer,
)
from pykit_messaging.protocols import MessageProducer


class DeadLetterProducer(_CoreDeadLetterProducer):
    """Kafka-compatible DLQ producer with the historic ``suffix=`` constructor."""

    def __init__(self, producer: MessageProducer, *, suffix: str = ".dlq") -> None:
        super().__init__(producer, DeadLetterConfig(suffix=suffix))


__all__ = ["DeadLetterConfig", "DeadLetterEnvelope", "DeadLetterProducer"]
