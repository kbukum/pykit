"""Extended tests for pykit-worker: edge cases, concurrency, and error handling."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC

import pytest

from pykit_worker import (
    Event,
    EventType,
    PoolConfig,
    Task,
    TaskResult,
    TaskStatus,
    WorkerPool,
)
from pykit_worker.event import (
    complete_event,
    error_event,
    log_event,
    partial_event,
    progress_event,
)


# ---------------------------------------------------------------------------
# 1. Task timeout enforcement (task exceeds timeout)
# ---------------------------------------------------------------------------


class TestTimeoutEnforcement:
    async def test_task_exceeds_config_timeout(self) -> None:
        pool = WorkerPool(PoolConfig(max_workers=2, task_timeout=0.1))
        task = await pool.submit("slow", self._slow_handler)
        result = await pool.wait(task.id)
        assert result.status == TaskStatus.FAILED
        assert result.error is not None
        assert "timed out" in result.error

    async def test_task_exceeds_per_wait_timeout(self) -> None:
        pool = WorkerPool(PoolConfig(max_workers=2))
        task = await pool.submit("slow", self._slow_handler)
        result = await pool.wait(task.id, timeout=0.1)
        assert result.status == TaskStatus.FAILED
        assert result.error is not None
        assert "timed out" in result.error

    async def test_fast_task_within_timeout(self) -> None:
        pool = WorkerPool(PoolConfig(max_workers=2, task_timeout=1.0))
        task = await pool.submit("fast", self._fast_handler)
        result = await pool.wait(task.id)
        assert result.status == TaskStatus.COMPLETED
        assert result.result == "done"

    @staticmethod
    async def _slow_handler() -> str:
        await asyncio.sleep(5.0)
        return "never"

    @staticmethod
    async def _fast_handler() -> str:
        return "done"


# ---------------------------------------------------------------------------
# 2. Task cancellation mid-execution
# ---------------------------------------------------------------------------


class TestCancellationMidExecution:
    async def test_cancel_running_task(self) -> None:
        started = asyncio.Event()

        async def handler() -> str:
            started.set()
            await asyncio.sleep(10.0)
            return "never"

        pool = WorkerPool(PoolConfig(max_workers=2))
        task = await pool.submit("block", handler)
        await started.wait()
        await pool.cancel(task.id)
        assert task.status == TaskStatus.CANCELLED

    async def test_cancel_already_completed_task(self) -> None:
        async def handler() -> int:
            return 42

        pool = WorkerPool(PoolConfig(max_workers=2))
        task = await pool.submit("quick", handler)
        result = await pool.wait(task.id)
        assert result.status == TaskStatus.COMPLETED
        # Cancel after completion: status should remain COMPLETED
        await pool.cancel(task.id)
        assert task.status == TaskStatus.COMPLETED


# ---------------------------------------------------------------------------
# 3. Submit after shutdown → error
# ---------------------------------------------------------------------------


class TestSubmitAfterShutdown:
    async def test_submit_after_graceful_shutdown(self) -> None:
        pool = WorkerPool(PoolConfig(max_workers=2))
        await pool.shutdown(graceful=True)
        with pytest.raises(RuntimeError, match="shut down"):
            await pool.submit("fail", self._noop)

    async def test_submit_after_forced_shutdown(self) -> None:
        pool = WorkerPool(PoolConfig(max_workers=2))
        await pool.shutdown(graceful=False)
        with pytest.raises(RuntimeError, match="shut down"):
            await pool.submit("fail", self._noop)

    @staticmethod
    async def _noop() -> None:
        pass


# ---------------------------------------------------------------------------
# 4. Concurrent submissions exceeding pool size (backpressure)
# ---------------------------------------------------------------------------


class TestBackpressure:
    async def test_more_tasks_than_workers(self) -> None:
        high_water = 0
        current = 0
        lock = asyncio.Lock()

        async def handler(delay: float) -> float:
            nonlocal high_water, current
            async with lock:
                current += 1
                if current > high_water:
                    high_water = current
            await asyncio.sleep(delay)
            async with lock:
                current -= 1
            return delay

        pool = WorkerPool(PoolConfig(max_workers=3))
        tasks = []
        for _ in range(9):
            t = await pool.submit("work", handler, 0.05)
            tasks.append(t)

        results = await asyncio.gather(*(pool.wait(t.id) for t in tasks))
        for r in results:
            assert r.status == TaskStatus.COMPLETED

        # Concurrency should never exceed max_workers
        assert high_water <= 3


# ---------------------------------------------------------------------------
# 5. Event stream ordering
# ---------------------------------------------------------------------------


class TestEventStreamOrdering:
    async def test_events_in_chronological_order(self) -> None:
        pool = WorkerPool(PoolConfig(max_workers=1))
        task = await pool.submit("ordered", self._handler)
        result = await pool.wait(task.id)
        timestamps = [e.timestamp for e in result.events]
        assert timestamps == sorted(timestamps)
        assert result.status == TaskStatus.COMPLETED

    @staticmethod
    async def _handler() -> str:
        return "ok"


# ---------------------------------------------------------------------------
# 6. TaskResult with exception details
# ---------------------------------------------------------------------------


class TestTaskResultExceptionDetails:
    async def test_exception_in_handler_captured(self) -> None:
        async def handler() -> None:
            msg = "something went wrong"
            raise ValueError(msg)

        pool = WorkerPool(PoolConfig(max_workers=1))
        task = await pool.submit("err", handler)
        result = await pool.wait(task.id)
        assert result.status == TaskStatus.FAILED
        assert result.error is not None
        assert "something went wrong" in result.error
        # Should have an error event
        error_events = [e for e in result.events if e.type == EventType.ERROR]
        assert len(error_events) >= 1


# ---------------------------------------------------------------------------
# 7. Pool shutdown with pending tasks → graceful drain
# ---------------------------------------------------------------------------


class TestGracefulDrain:
    async def test_graceful_shutdown_completes_tasks(self) -> None:
        completed = []

        async def handler(idx: int) -> int:
            await asyncio.sleep(0.05)
            completed.append(idx)
            return idx

        pool = WorkerPool(PoolConfig(max_workers=2, graceful_timeout=5.0))
        for i in range(4):
            await pool.submit(f"task-{i}", handler, i)

        await pool.shutdown(graceful=True)
        assert len(completed) == 4


# ---------------------------------------------------------------------------
# 8. Very fast tasks (microsecond completion)
# ---------------------------------------------------------------------------


class TestFastTasks:
    async def test_microsecond_tasks(self) -> None:
        async def handler() -> int:
            return 1

        pool = WorkerPool(PoolConfig(max_workers=4))
        tasks = [await pool.submit(f"fast-{i}", handler) for i in range(50)]
        results = await asyncio.gather(*(pool.wait(t.id) for t in tasks))
        for r in results:
            assert r.status == TaskStatus.COMPLETED
            assert r.result == 1


# ---------------------------------------------------------------------------
# 9. Very slow tasks (second-level timeout)
# ---------------------------------------------------------------------------


class TestSlowTaskTimeout:
    async def test_slow_task_hits_timeout(self) -> None:
        async def handler() -> str:
            await asyncio.sleep(10.0)
            return "never"

        pool = WorkerPool(PoolConfig(max_workers=1, task_timeout=0.2))
        task = await pool.submit("slow", handler)
        start = time.monotonic()
        result = await pool.wait(task.id)
        elapsed = time.monotonic() - start
        assert result.status == TaskStatus.FAILED
        assert elapsed < 2.0  # should not wait the full 10s


# ---------------------------------------------------------------------------
# 10. Pool stats accuracy during concurrent ops
# ---------------------------------------------------------------------------


class TestPoolStatsAccuracy:
    async def test_active_and_pending_during_execution(self) -> None:
        barrier = asyncio.Event()

        async def handler() -> None:
            await barrier.wait()

        pool = WorkerPool(PoolConfig(max_workers=2))
        tasks = [await pool.submit(f"t-{i}", handler) for i in range(4)]

        # Give semaphore time to be acquired
        await asyncio.sleep(0.05)
        assert pool.active_count <= 2
        assert pool.pending_count >= 0

        barrier.set()
        for t in tasks:
            await pool.wait(t.id)


# ---------------------------------------------------------------------------
# 11. EventType enum completeness
# ---------------------------------------------------------------------------


class TestEventTypeEnum:
    def test_all_event_types_present(self) -> None:
        expected = {"progress", "partial", "complete", "error", "log"}
        actual = {e.value for e in EventType}
        assert actual == expected

    def test_event_type_str_values(self) -> None:
        assert str(EventType.PROGRESS) == "progress"
        assert str(EventType.COMPLETE) == "complete"
        assert str(EventType.ERROR) == "error"


# ---------------------------------------------------------------------------
# 12. Task status transitions
# ---------------------------------------------------------------------------


class TestTaskStatusTransitions:
    async def test_pending_to_running_to_completed(self) -> None:
        running_event = asyncio.Event()
        was_running = False

        async def handler() -> str:
            nonlocal was_running
            was_running = True
            running_event.set()
            return "ok"

        pool = WorkerPool(PoolConfig(max_workers=1))
        task = await pool.submit("transition", handler)
        assert task.status == TaskStatus.PENDING

        result = await pool.wait(task.id)
        assert was_running
        assert result.status == TaskStatus.COMPLETED

    async def test_pending_to_running_to_failed(self) -> None:
        async def handler() -> None:
            msg = "boom"
            raise RuntimeError(msg)

        pool = WorkerPool(PoolConfig(max_workers=1))
        task = await pool.submit("fail-transition", handler)
        result = await pool.wait(task.id)
        assert result.status == TaskStatus.FAILED


# ---------------------------------------------------------------------------
# 13. Cancel unknown task → KeyError
# ---------------------------------------------------------------------------


class TestCancelUnknownTask:
    async def test_cancel_nonexistent_raises_key_error(self) -> None:
        pool = WorkerPool(PoolConfig(max_workers=1))
        with pytest.raises(KeyError, match="unknown task"):
            await pool.cancel("nonexistent-id")


# ---------------------------------------------------------------------------
# 14. Wait on unknown task → KeyError
# ---------------------------------------------------------------------------


class TestWaitUnknownTask:
    async def test_wait_nonexistent_raises_key_error(self) -> None:
        pool = WorkerPool(PoolConfig(max_workers=1))
        with pytest.raises(KeyError, match="unknown task"):
            await pool.wait("nonexistent-id")


# ---------------------------------------------------------------------------
# 15. Event factory functions produce correct types
# ---------------------------------------------------------------------------


class TestEventFactories:
    def test_progress_event_factory(self) -> None:
        e = progress_event("t1", data=50, message="half")
        assert e.type == EventType.PROGRESS
        assert e.task_id == "t1"
        assert e.data == 50
        assert e.message == "half"

    def test_partial_event_factory(self) -> None:
        e = partial_event("t2", data={"chunk": 1})
        assert e.type == EventType.PARTIAL
        assert e.data == {"chunk": 1}

    def test_complete_event_factory(self) -> None:
        e = complete_event("t3", data="result")
        assert e.type == EventType.COMPLETE
        assert e.data == "result"

    def test_error_event_factory(self) -> None:
        e = error_event("t4", message="failure")
        assert e.type == EventType.ERROR
        assert e.message == "failure"

    def test_log_event_factory(self) -> None:
        e = log_event("t5", message="info")
        assert e.type == EventType.LOG
        assert e.message == "info"


# ---------------------------------------------------------------------------
# 16. Task defaults and uniqueness
# ---------------------------------------------------------------------------


class TestTaskDefaults:
    def test_task_defaults(self) -> None:
        t = Task(name="my-task")
        assert t.status == TaskStatus.PENDING
        assert len(t.id) == 32  # uuid4().hex
        assert t.created_at.tzinfo is not None

    def test_task_ids_unique(self) -> None:
        ids = {Task(name="t").id for _ in range(100)}
        assert len(ids) == 100

    def test_task_result_defaults(self) -> None:
        r = TaskResult(task_id="x", status=TaskStatus.COMPLETED)
        assert r.result is None
        assert r.error is None
        assert r.events == []
        assert r.duration == 0.0


# ---------------------------------------------------------------------------
# 17. Graceful timeout enforcement during shutdown
# ---------------------------------------------------------------------------


class TestGracefulTimeoutEnforcement:
    async def test_shutdown_cancels_after_timeout(self) -> None:
        async def handler() -> None:
            await asyncio.sleep(60.0)  # very long

        pool = WorkerPool(PoolConfig(max_workers=1, graceful_timeout=0.2))
        await pool.submit("stuck", handler)
        await asyncio.sleep(0.05)  # let it start

        start = time.monotonic()
        await pool.shutdown(graceful=True)
        elapsed = time.monotonic() - start
        assert elapsed < 2.0  # should not wait 60s


# ---------------------------------------------------------------------------
# 18. Duration is recorded in TaskResult
# ---------------------------------------------------------------------------


class TestDurationRecorded:
    async def test_duration_is_positive(self) -> None:
        async def handler() -> int:
            await asyncio.sleep(0.05)
            return 1

        pool = WorkerPool(PoolConfig(max_workers=1))
        task = await pool.submit("dur", handler)
        result = await pool.wait(task.id)
        assert result.status == TaskStatus.COMPLETED
        assert result.duration > 0.0
