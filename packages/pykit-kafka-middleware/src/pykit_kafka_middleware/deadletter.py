"""Dead-letter queue producer for failed Kafka messages."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from pykit_kafka.producer import KafkaProducer
from pykit_kafka.types import Message


@dataclass
class DeadLetterEnvelope:
    """Envelope written to the DLQ topic."""

    original_topic: str
    error: str
    retry_count: int
    timestamp: str
    headers: dict[str, str] = field(default_factory=dict)
    payload: str = ""


class DeadLetterProducer:
    """Sends failed messages to a dead-letter queue topic.

    The DLQ topic name is ``{original_topic}{suffix}`` where suffix
    defaults to ``".dlq"``.
    """

    def __init__(self, producer: KafkaProducer, *, suffix: str = ".dlq") -> None:
        self._producer = producer
        self._suffix = suffix

    async def send(self, msg: Message, error: Exception) -> None:
        """Publish a dead-letter envelope for the failed message."""
        retry_count = 0
        rc = msg.headers.get("x-retry-count", "")
        if rc.isdigit():
            retry_count = int(rc)

        envelope = DeadLetterEnvelope(
            original_topic=msg.topic,
            error=str(error),
            retry_count=retry_count,
            timestamp=datetime.now(UTC).isoformat(),
            headers=dict(msg.headers),
            payload=msg.value.decode(errors="replace"),
        )

        dlq_topic = msg.topic + self._suffix
        key = msg.key or "dlq"

        payload = json.dumps({
            "original_topic": envelope.original_topic,
            "error": envelope.error,
            "retry_count": envelope.retry_count,
            "timestamp": envelope.timestamp,
            "headers": envelope.headers,
            "payload": envelope.payload,
        }).encode()

        await self._producer.send(dlq_topic, value=payload, key=key)
