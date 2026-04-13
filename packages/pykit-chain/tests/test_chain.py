"""Comprehensive tests for pykit-chain."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from pykit_chain import (
    ChainBuilder,
    Operation,
    StepProgress,
    StepStatus,
)

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


@dataclass
class IncrementOp:
    """Increments an integer input by 1."""

    id: str
    name: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            self.name = self.id

    async def execute(self, input: Any, progress: Any) -> Any:
        n = input if isinstance(input, int) else 0
        progress(50, "halfway")
        progress(100, None)
        return n + 1

    async def cleanup(self, output: Any) -> None:
        pass


@dataclass
class FailOp:
    """Always raises an error."""

    id: str
    name: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            self.name = self.id

    async def execute(self, input: Any, progress: Any) -> Any:
        raise RuntimeError("intentional failure")

    async def cleanup(self, output: Any) -> None:
        pass


@dataclass
class CleanupTracker:
    """Tracks whether cleanup was called."""

    id: str
    cleaned: bool = False
    name: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            self.name = self.id

    async def execute(self, input: Any, progress: Any) -> Any:
        return input

    async def cleanup(self, output: Any) -> None:
        self.cleaned = True


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSimpleChain:
    @pytest.mark.asyncio
    async def test_increments(self) -> None:
        chain = (
            ChainBuilder()
            .step(IncrementOp(id="step-1"))
            .step(IncrementOp(id="step-2"))
            .step(IncrementOp(id="step-3"))
            .build()
        )

        result = await chain.execute(0)

        assert result.success
        assert result.completed_steps == 3
        assert result.final_output == 3
        assert result.failed_step is None

        for i, step in enumerate(result.steps):
            assert step.status == StepStatus.COMPLETED
            assert step.output == i + 1


class TestFailureCleanup:
    @pytest.mark.asyncio
    async def test_failure_triggers_cleanup(self) -> None:
        tracker1 = CleanupTracker(id="tracker-1")
        tracker2 = CleanupTracker(id="tracker-2")

        chain = (
            ChainBuilder()
            .step(tracker1)
            .step(FailOp(id="fail-op"))
            .step(tracker2)
            .cleanup_on_failure(True)
            .stop_on_failure(True)
            .build()
        )

        result = await chain.execute(None)

        assert not result.success
        assert result.completed_steps == 1
        assert result.final_output is None

        # Step 0 completed, step 1 failed, step 2 skipped
        assert result.steps[0].status == StepStatus.COMPLETED
        assert result.steps[1].status == StepStatus.FAILED
        assert result.steps[2].status == StepStatus.SKIPPED

        # Cleanup should have run on the completed tracker-1
        assert tracker1.cleaned
        # tracker-2 was skipped, so no cleanup
        assert not tracker2.cleaned


class TestCancellation:
    @pytest.mark.asyncio
    async def test_marks_remaining_cancelled(self) -> None:
        cancel = asyncio.Event()
        cancel.set()  # Cancel before the chain runs

        chain = (
            ChainBuilder()
            .step(IncrementOp(id="step-1"))
            .step(IncrementOp(id="step-2"))
            .step(IncrementOp(id="step-3"))
            .build()
        )

        result = await chain.execute(0, cancel=cancel)

        assert not result.success
        assert result.completed_steps == 0

        for step in result.steps:
            assert step.status == StepStatus.CANCELLED
            assert step.error == "chain cancelled"


class TestContinueAfterFailure:
    @pytest.mark.asyncio
    async def test_all_steps_run(self) -> None:
        chain = (
            ChainBuilder()
            .step(IncrementOp(id="step-1"))
            .step(FailOp(id="fail-op"))
            .step(IncrementOp(id="step-3"))
            .stop_on_failure(False)
            .cleanup_on_failure(False)
            .build()
        )

        result = await chain.execute(0)

        assert not result.success
        # step-1 completed, fail-op failed, step-3 still ran
        assert result.steps[0].status == StepStatus.COMPLETED
        assert result.steps[1].status == StepStatus.FAILED
        assert result.steps[2].status == StepStatus.COMPLETED
        assert result.completed_steps == 2


class TestProgressEvents:
    @pytest.mark.asyncio
    async def test_callback_events(self) -> None:
        events: list[StepProgress] = []

        chain = ChainBuilder().step(IncrementOp(id="step-1")).step(IncrementOp(id="step-2")).build()

        result = await chain.execute(0, progress=lambda p: events.append(p))

        assert result.success

        # For each step: Running(0%), Running(50%), Running(100%), Completed(100%)
        # = 4 events per step x 2 steps = 8 total
        assert len(events) == 8

        # First step events
        assert events[0].step_id == "step-1"
        assert events[0].status == StepStatus.RUNNING
        assert events[0].progress_percent == 0

        assert events[1].step_id == "step-1"
        assert events[1].status == StepStatus.RUNNING
        assert events[1].progress_percent == 50

        assert events[2].step_id == "step-1"
        assert events[2].status == StepStatus.RUNNING
        assert events[2].progress_percent == 100

        assert events[3].step_id == "step-1"
        assert events[3].status == StepStatus.COMPLETED
        assert events[3].progress_percent == 100

        # Second step events
        assert events[4].step_id == "step-2"
        assert events[4].status == StepStatus.RUNNING
        assert events[4].progress_percent == 0

        assert events[7].step_id == "step-2"
        assert events[7].status == StepStatus.COMPLETED
        assert events[7].progress_percent == 100


class TestEmptyChain:
    @pytest.mark.asyncio
    async def test_empty_succeeds(self) -> None:
        chain = ChainBuilder().build()
        result = await chain.execute("input")

        assert result.success
        assert len(result.steps) == 0


class TestOperationProtocol:
    def test_dataclass_satisfies_protocol(self) -> None:
        op = IncrementOp(id="test")
        assert isinstance(op, Operation)
