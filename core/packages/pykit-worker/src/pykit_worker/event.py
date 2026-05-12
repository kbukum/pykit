"""Event types emitted by workers during task execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    """Identifies the kind of event emitted by a handler."""

    PROGRESS = "progress"
    PARTIAL = "partial"
    COMPLETE = "complete"
    ERROR = "error"
    LOG = "log"


@dataclass
class Event:
    """A message emitted by a handler during execution."""

    type: EventType
    task_id: str
    data: Any = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    message: str = ""


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def progress_event(task_id: str, data: Any = None, *, message: str = "") -> Event:
    """Create a progress event."""
    return Event(type=EventType.PROGRESS, task_id=task_id, data=data, message=message)


def partial_event(task_id: str, data: Any = None, *, message: str = "") -> Event:
    """Create a partial-result event."""
    return Event(type=EventType.PARTIAL, task_id=task_id, data=data, message=message)


def complete_event(task_id: str, data: Any = None, *, message: str = "") -> Event:
    """Create a completion event."""
    return Event(type=EventType.COMPLETE, task_id=task_id, data=data, message=message)


def error_event(task_id: str, data: Any = None, *, message: str = "") -> Event:
    """Create an error event."""
    return Event(type=EventType.ERROR, task_id=task_id, data=data, message=message)


def log_event(task_id: str, data: Any = None, *, message: str = "") -> Event:
    """Create a log event."""
    return Event(type=EventType.LOG, task_id=task_id, data=data, message=message)
