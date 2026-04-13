"""Result and progress types for chain execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class StepStatus(StrEnum):
    """Status of a single step in a chain."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass
class StepProgress:
    """Progress update for a single step."""

    step_index: int
    step_id: str
    status: StepStatus
    progress_percent: int  # 0-100
    message: str | None = None


@dataclass
class StepResult:
    """Result of a single step execution."""

    step_id: str
    status: StepStatus
    duration: float = 0.0  # seconds
    output: Any = None
    error: str | None = None


@dataclass
class ChainResult:
    """Overall chain execution result."""

    steps: list[StepResult] = field(default_factory=list)
    total_duration: float = 0.0  # seconds
    final_output: Any = None
    success: bool = False

    @property
    def completed_steps(self) -> int:
        """Number of steps that completed successfully."""
        return sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)

    @property
    def failed_step(self) -> StepResult | None:
        """First failed step, or ``None``."""
        for s in self.steps:
            if s.status == StepStatus.FAILED:
                return s
        return None
