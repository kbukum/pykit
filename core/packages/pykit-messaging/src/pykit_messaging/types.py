"""Message and event types."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from pykit_util import JsonCodec

JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


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
    data: JsonValue = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_json(self) -> bytes:
        """Serialize event to JSON bytes."""
        payload: dict[str, JsonValue] = {
            "id": self.id,
            "type": self.type,
            "source": self.source,
            "subject": self.subject,
            "content_type": self.content_type,
            "version": self.version,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }
        return JsonCodec[dict[str, JsonValue]](stringify_unknown=False).encode(payload)

    @classmethod
    def from_json(cls, raw: bytes) -> Event:
        """Deserialize event from JSON bytes."""
        payload = JsonCodec[dict[str, JsonValue]]().decode(raw)
        return cls(
            id=_required_str(payload, "id"),
            type=_required_str(payload, "type"),
            source=_required_str(payload, "source"),
            timestamp=datetime.fromisoformat(_required_str(payload, "timestamp")),
            subject=_optional_str(payload, "subject", ""),
            content_type=_optional_str(payload, "content_type", "application/json"),
            version=_optional_str(payload, "version", "1.0"),
            data=payload.get("data"),
        )


MessageHandler = Callable[[Message], Awaitable[None]]
EventHandler = Callable[[Event], Awaitable[None]]


def _required_str(payload: dict[str, JsonValue], key: str) -> str:
    value = payload[key]
    if not isinstance(value, str):
        raise ValueError(f"event field '{key}' must be a string")
    return value


def _optional_str(payload: dict[str, JsonValue], key: str, default: str) -> str:
    value = payload.get(key, default)
    if not isinstance(value, str):
        raise ValueError(f"event field '{key}' must be a string")
    return value
