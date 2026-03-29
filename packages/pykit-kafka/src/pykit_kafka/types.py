"""Message and event types."""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class Message:
    """A Kafka message."""

    key: str | None
    value: bytes
    topic: str
    partition: int
    offset: int
    timestamp: datetime | None = None
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class Event:
    """A structured event envelope for Kafka messages."""

    type: str
    source: str
    subject: str = ""
    data: Any = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_json(self) -> bytes:
        """Serialize event to JSON bytes."""
        payload = {
            "id": self.id,
            "type": self.type,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "subject": self.subject,
            "data": self.data,
        }
        return json.dumps(payload).encode()

    @classmethod
    def from_json(cls, raw: bytes) -> Event:
        """Deserialize event from JSON bytes."""
        d = json.loads(raw)
        return cls(
            id=d["id"],
            type=d["type"],
            source=d["source"],
            timestamp=datetime.fromisoformat(d["timestamp"]),
            subject=d.get("subject", ""),
            data=d.get("data"),
        )


MessageHandler = Callable[[Message], Awaitable[None]]
EventHandler = Callable[[Event], Awaitable[None]]
