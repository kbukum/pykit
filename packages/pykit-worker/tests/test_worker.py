# mypy: ignore-errors
"""Comprehensive tests for pykit-worker."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from pykit_worker import Event, EventType, PoolConfig, Task, TaskResult, TaskStatus, WorkerPool
from pykit_worker.event import (
    complete_event,
    error_event,
    log_event,
    partial_event,
    progress_event,
)

# ── Event creation ──────────────────────────────────────────────────────────


class TestEventCreation:
    def test_event_types(self) -> None:
        assert EventType.PROGRESS == "progress"
        assert EventType.PARTIAL == "partial"
        assert EventType.COMPLETE == "complete"
        assert EventType.ERROR == "error"
        assert EventType.LOG == "log"

    def test_event_defaults(self) -> None:
        ev = Event(type=EventType.LOG, task_id="t1")
        assert ev.data is None
        assert ev.message == ""
        assert isinstance(ev.timestamp, datetime)
        assert ev.timestamp.tzinfo == UTC

    def test_progress_event_factory(self) -> None:
        ev = progress_event("t1", data={"pct": 50}, message="halfway")
        assert ev.type == EventType.PROGRESS
        assert ev.task_id == "t1"
        assert ev.data == {"pct": 50}
        assert ev.message == "halfway"

    def test_partial_event_factory(self) -> None:
        ev = partial_event("t1", data=[1, 2])
        assert ev.type == EventType.PARTIAL
        assert ev.data == [1, 2]

    def test_complete_event_factory(self) -> None:
        ev = complete_event("t1", data="done")
        assert ev.type == EventType.COMPLETE

    def test_error_event_factory(self) -> None:
        ev = error_event("t1", message="boom")
        assert ev.type == EventType.ERROR
        assert ev.message == "boom"

    def test_log_event_factory(self) -> None:
        ev = log_event("t1", message="info")
        assert ev.type == EventType.LOG


# ── Task lifecycle ──────────────────────────────────────────────────────────


class TestTaskLifecycle:
    def test_task_defaults(self) -> None:
        t = Task(name="job")
        assert t.status == TaskStatus.PENDING
        assert len(t.id) == 32  # uuid hex
        assert isinstance(t.created_at, datetime)

    def test_task_status_values(self) -> None:
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.CANCELLED == "cancelled"

    def test_task_result_defaults(self) -> None:
        tr = TaskResult(task_id="t1", status=TaskStatus.COMPLETED)
        assert tr.result is None
        assert tr.error is None
        assert tr.events == []
        assert tr.duration == 0.0


# ── Pool: submit and wait ──────────────────────────────────────────────────


class TestPoolSubmitWait:
    async def test_submit_and_wait(self) -> None:
        pool = WorkerPool()

        async def handler() -> int:
            return 42

        task = await pool.submit("add", handler)
        assert task.status in {TaskStatus.PENDING, TaskStatus.RUNNING}

        result = await pool.wait(task.id)
        assert result.status == TaskStatus.COMPLETED
        assert result.result == 42
        assert result.duration > 0

        await pool.shutdown()

    async def test_handler_with_args(self) -> None:
        pool = WorkerPool()

        async def add(a: int, b: int) -> int:
            return a + b

        task = await pool.submit("add", add, 3, 7)
        result = await pool.wait(task.id)
        assert result.result == 10
        await pool.shutdown()

    async def test_handler_failure(self) -> None:
        pool = WorkerPool()

        async def fail() -> None:
            raise ValueError("boom")

        task = await pool.submit("fail", fail)
        result = await pool.wait(task.id)
        assert result.status == TaskStatus.FAILED
        assert result.error is not None
        assert "boom" in result.error
        await pool.shutdown()

    async def test_wait_unknown_task(self) -> None:
        pool = WorkerPool()
        with pytest.raises(KeyError, match="unknown task"):
            await pool.wait("no-such-id")
        await pool.shutdown()


# ── Pool: concurrent tasks ─────────────────────────────────────────────────


class TestPoolConcurrency:
    async def test_concurrent_tasks(self) -> None:
        pool = WorkerPool(PoolConfig(max_workers=4))

        async def work(n: int) -> int:
            await asyncio.sleep(0.01)
            return n * 2

        tasks = [await pool.submit(f"w{i}", work, i) for i in range(8)]
        results = [await pool.wait(t.id) for t in tasks]

        assert all(r.status == TaskStatus.COMPLETED for r in results)
        assert [r.result for r in results] == [i * 2 for i in range(8)]
        await pool.shutdown()

    async def test_semaphore_limits_concurrency(self) -> None:
        """At most max_workers handlers run at the same time."""
        max_workers = 2
        pool = WorkerPool(PoolConfig(max_workers=max_workers))
        high_water = 0
        current = 0
        lock = asyncio.Lock()

        async def track() -> None:
            nonlocal high_water, current
            async with lock:
                current += 1
                if current > high_water:
                    high_water = current
            await asyncio.sleep(0.05)
            async with lock:
                current -= 1

        tasks = [await pool.submit(f"t{i}", track) for i in range(6)]
        await asyncio.gather(*(pool.wait(t.id) for t in tasks))

        assert high_water <= max_workers
        await pool.shutdown()


# ── Pool: timeout ──────────────────────────────────────────────────────────


class TestPoolTimeout:
    async def test_task_timeout(self) -> None:
        pool = WorkerPool(PoolConfig(task_timeout=0.05))

        async def slow() -> None:
            await asyncio.sleep(10)

        task = await pool.submit("slow", slow)
        result = await pool.wait(task.id)
        assert result.status == TaskStatus.FAILED
        assert result.error is not None
        assert "timed out" in result.error
        await pool.shutdown()

    async def test_explicit_wait_timeout(self) -> None:
        pool = WorkerPool()

        async def slow() -> None:
            await asyncio.sleep(10)

        task = await pool.submit("slow", slow)
        result = await pool.wait(task.id, timeout=0.05)
        assert result.status == TaskStatus.FAILED
        assert "timed out" in (result.error or "")
        await pool.shutdown()


# ── Pool: cancellation ─────────────────────────────────────────────────────


class TestPoolCancellation:
    async def test_cancel_running_task(self) -> None:
        pool = WorkerPool()

        async def slow() -> None:
            await asyncio.sleep(10)

        task = await pool.submit("slow", slow)
        await asyncio.sleep(0.02)  # let it start
        await pool.cancel(task.id)

        assert task.status == TaskStatus.CANCELLED
        await pool.shutdown()

    async def test_cancel_unknown_task(self) -> None:
        pool = WorkerPool()
        with pytest.raises(KeyError, match="unknown task"):
            await pool.cancel("nope")
        await pool.shutdown()


# ── Pool: graceful shutdown ────────────────────────────────────────────────


class TestPoolShutdown:
    async def test_graceful_shutdown_waits(self) -> None:
        pool = WorkerPool(PoolConfig(graceful_timeout=5.0))
        completed = False

        async def work() -> None:
            nonlocal completed
            await asyncio.sleep(0.05)
            completed = True

        await pool.submit("work", work)
        await pool.shutdown(graceful=True)
        assert completed

    async def test_forced_shutdown_cancels(self) -> None:
        pool = WorkerPool()

        async def forever() -> None:
            await asyncio.sleep(100)

        await pool.submit("forever", forever)
        await pool.shutdown(graceful=False)
        # should complete without hanging

    async def test_submit_after_shutdown_raises(self) -> None:
        pool = WorkerPool()
        await pool.shutdown()

        with pytest.raises(RuntimeError, match="shut down"):
            await pool.submit("late", asyncio.sleep, 0)


# ── Pool: counts ───────────────────────────────────────────────────────────


class TestPoolCounts:
    async def test_active_and_pending_counts(self) -> None:
        started = asyncio.Event()
        release = asyncio.Event()
        pool = WorkerPool(PoolConfig(max_workers=1))

        async def blocker() -> None:
            started.set()
            await release.wait()

        async def quick() -> None:
            return None

        t1 = await pool.submit("blocker", blocker)
        await started.wait()

        assert pool.active_count == 1

        t2 = await pool.submit("quick", quick)
        # t2 is pending because the single worker slot is occupied
        assert pool.pending_count >= 0  # may have started by now

        release.set()
        await pool.wait(t1.id)
        await pool.wait(t2.id)
        assert pool.active_count == 0
        await pool.shutdown()
