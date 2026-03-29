"""Node abstraction for DAG execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable


class NodeStatus(StrEnum):
    """Execution status of a node."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class NodeState:
    """Tracks execution state for a single node."""

    status: NodeStatus = NodeStatus.PENDING
    result: Any = None
    error: Exception | None = None
    duration: float = 0.0


@runtime_checkable
class Node(Protocol):
    """A processing unit in a DAG."""

    @property
    def name(self) -> str: ...

    @property
    def dependencies(self) -> list[str]: ...

    async def execute(self, inputs: dict[str, Any]) -> Any: ...
