"""Task tracking primitives for the worker pool."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pykit_worker.event import Event


class TaskStatus(StrEnum):
    """Lifecycle status of a task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Lightweight handle representing a submitted unit of work."""

    name: str
    id: str = field(default_factory=lambda: uuid4().hex)
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class TaskResult:
    """Outcome of a completed task."""

    task_id: str
    status: TaskStatus
    result: Any = None
    error: str | None = None
    events: list[Event] = field(default_factory=list)
    duration: float = 0.0
