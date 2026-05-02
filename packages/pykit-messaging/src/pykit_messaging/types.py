"""Message and event types."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pykit_util import JsonCodec


@dataclass
class Message:
    """A message envelope."""

    key: str | None
    value: bytes
    topic: str
    partition: int
    offset: int
    timestamp: datetime | None = None
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class Event:
    """A structured event envelope for messages."""

    type: str
    source: str
    subject: str = ""
    content_type: str = "application/json"
    version: str = "1.0"
    data: Any = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_json(self) -> bytes:
        """Serialize event to JSON bytes."""
        payload: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "source": self.source,
            "subject": self.subject,
            "content_type": self.content_type,
            "version": self.version,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }
        return JsonCodec[dict[str, Any]](stringify_unknown=False).encode(payload)

    @classmethod
    def from_json(cls, raw: bytes) -> Event:
        """Deserialize event from JSON bytes."""
        d = JsonCodec[dict[str, Any]]().decode(raw)
        return cls(
            id=d["id"],
            type=d["type"],
            source=d["source"],
            timestamp=datetime.fromisoformat(d["timestamp"]),
            subject=d.get("subject", ""),
            content_type=d.get("content_type", "application/json"),
            version=d.get("version", "1.0"),
            data=d.get("data"),
        )


MessageHandler = Callable[[Message], Awaitable[None]]
EventHandler = Callable[[Event], Awaitable[None]]
