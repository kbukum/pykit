"""Core interfaces and types for lifecycle-managed components."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable


class State(enum.IntEnum):
    """Lifecycle state for a registered component."""

    CREATED = 0
    STARTING = 1
    RUNNING = 2
    STOPPING = 3
    STOPPED = 4
    FAILED = 5

    def __str__(self) -> str:
        """Return the lowercase state name."""
        return self.name.lower()


class HealthStatus(enum.StrEnum):
    """Health state of a component."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass(frozen=True)
class Health:
    """Health information for a component."""

    name: str
    status: HealthStatus
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@runtime_checkable
class Component(Protocol):
    """Lifecycle-managed infrastructure component."""

    @property
    def name(self) -> str: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def health(self) -> Health: ...


@dataclass(frozen=True)
class Description:
    """Summary information for the bootstrap display."""

    name: str
    type: str
    details: str = ""
    port: int = 0


class Describable(Protocol):
    """Optionally implemented by components to provide startup summary info."""

    def describe(self) -> Description: ...
