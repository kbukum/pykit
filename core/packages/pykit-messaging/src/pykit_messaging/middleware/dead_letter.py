"""Dead-letter queue middleware for message handlers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from pykit_messaging.protocols import MessageProducer
from pykit_messaging.types import Message
from pykit_util import JsonCodec

_SENSITIVE_HEADER_PARTS = (
    "authorization",
    "cookie",
    "token",
    "secret",
    "password",
    "credential",
    "api-key",
    "apikey",
)
_MAX_DLQ_PAYLOAD_CHARS = 4096
_REDACTED = "<redacted>"


@dataclass(frozen=True)
class DeadLetterConfig:
    """Configuration for dead-letter routing."""

    suffix: str = ".dlq"


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
    """Routes terminally failed messages to a dead-letter topic."""

    def __init__(
        self,
        producer: MessageProducer,
        config: DeadLetterConfig | None = None,
    ) -> None:
        self._producer = producer
        self._config = config or DeadLetterConfig()

    async def send(self, msg: Message, error: Exception) -> None:
        """Send a failed message envelope to the dead-letter queue."""
        retry_count = 0
        rc = msg.headers.get("x-retry-count", "")
        if rc.isdigit():
            retry_count = int(rc)

        envelope = DeadLetterEnvelope(
            original_topic=msg.topic,
            error=_sanitize_summary(str(error)),
            retry_count=retry_count,
            timestamp=datetime.now(UTC).isoformat(),
            headers=_redact_headers(msg.headers),
            payload=_payload_summary(msg.value),
        )
        payload = JsonCodec[dict[str, object]]().encode(
            {
                "original_topic": envelope.original_topic,
                "error": envelope.error,
                "retry_count": envelope.retry_count,
                "timestamp": envelope.timestamp,
                "headers": envelope.headers,
                "payload": envelope.payload,
            }
        )

        await self._producer.send(
            msg.topic + self._config.suffix,
            value=payload,
            key=msg.key or "dlq",
        )


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        key: (_REDACTED if _is_sensitive(key) or _is_sensitive(value) else value)
        for key, value in headers.items()
    }


def _sanitize_summary(value: str) -> str:
    if _is_sensitive(value):
        return _REDACTED
    return _truncate(value)


def _payload_summary(value: bytes) -> str:
    text = value.decode(errors="replace")
    if _is_sensitive(text):
        return _REDACTED
    return _truncate(text)


def _truncate(value: str) -> str:
    if len(value) <= _MAX_DLQ_PAYLOAD_CHARS:
        return value
    return value[:_MAX_DLQ_PAYLOAD_CHARS] + "…"


def _is_sensitive(value: str) -> bool:
    lowered = value.lower()
    return any(part in lowered for part in _SENSITIVE_HEADER_PARTS)
