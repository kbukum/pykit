"""Dead-letter queue middleware for message handlers."""

from __future__ import annotations

from dataclasses import dataclass

from pykit_messaging.protocols import MessageProducer
from pykit_messaging.types import Message


@dataclass(frozen=True)
class DeadLetterConfig:
    """Configuration for dead-letter routing.

    Args:
        suffix: Suffix to append to topic name for the dead-letter queue.
    """

    suffix: str = ".dlq"


class DeadLetterProducer:
    """Routes failed messages to a dead-letter topic.

    The DLQ topic is derived from the original message topic by appending
    the configured suffix (default: ``.dlq``). Error details are stored
    in message headers.

    Args:
        producer: The message producer to send DLQ messages with.
        config: Optional dead-letter configuration; defaults to ``DeadLetterConfig()``.
    """

    def __init__(
        self,
        producer: MessageProducer,
        config: DeadLetterConfig | None = None,
    ) -> None:
        self._producer = producer
        self._config = config or DeadLetterConfig()

    async def send(self, msg: Message, error: Exception) -> None:
        """Send a failed message to the dead-letter queue.

        The error message is added to headers under ``x-dlq-error``, and the
        original topic is recorded under ``x-dlq-original-topic``.

        Args:
            msg: The message that failed processing.
            error: The exception that caused the failure.
        """
        dlq_topic = msg.topic + self._config.suffix
        headers = dict(msg.headers) if msg.headers else {}
        headers["x-dlq-error"] = str(error)
        headers["x-dlq-original-topic"] = msg.topic

        await self._producer.send(
            topic=dlq_topic,
            value=msg.value,
            key=msg.key,
            headers=headers,
        )
