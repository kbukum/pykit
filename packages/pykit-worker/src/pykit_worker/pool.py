"""Async worker pool with concurrency control and event collection."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pykit_worker.event import Event, EventType, complete_event, error_event
from pykit_worker.task import Task, TaskResult, TaskStatus


class OverflowPolicy(StrEnum):
    """How the pool responds when its pending-task limit is reached."""

    BLOCK = "block"
    REJECT = "reject"
    DROP_OLDEST = "drop_oldest"


class DispatchStrategy(StrEnum):
    """How newly submitted tasks are mapped onto worker slots."""

    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"


class PoolOverflowError(RuntimeError):
    """Raised when the worker pool cannot accept more tasks."""


@dataclass
class PoolConfig:
    """Configuration for :class:`WorkerPool`."""

    max_workers: int = 10
    task_timeout: float | None = None
    graceful_timeout: float = 30.0
    max_pending_tasks: int | None = None
    overflow_policy: OverflowPolicy = OverflowPolicy.BLOCK
    dispatch_strategy: DispatchStrategy = DispatchStrategy.ROUND_ROBIN

    def __post_init__(self) -> None:
        if self.max_workers < 1:
            raise ValueError("max_workers must be at least 1")


class _QueueState(StrEnum):
    QUEUED = "queued"
    ACQUIRING = "acquiring"
    RUNNING = "running"
    DONE = "done"


@dataclass
class _TaskEntry:
    task: Task
    handler: Callable[..., Coroutine[Any, Any, Any]]
    args: tuple[Any, ...]
    slot_index: int
    future: asyncio.Task[Any] | None = None
    events: list[Event] = field(default_factory=list)
    start_time: float = 0.0
    queue_state: _QueueState = _QueueState.QUEUED


class WorkerPool:
    """Async task pool with virtual worker slots and bounded pending capacity."""

    def __init__(self, config: PoolConfig | None = None) -> None:
        self._config = config or PoolConfig()
        self._slot_semaphores = [asyncio.Semaphore(1) for _ in range(self._config.max_workers)]
        self._slot_loads = [0 for _ in self._slot_semaphores]
        self._tasks: dict[str, _TaskEntry] = {}
        self._pending_order: deque[str] = deque()
        self._shutdown = False
        self._dispatch_counter = 0
        self._lock = asyncio.Lock()
        self._capacity_condition = asyncio.Condition(self._lock)

    @property
    def active_count(self) -> int:
        """Number of tasks currently running."""
        return sum(1 for entry in self._tasks.values() if entry.task.status == TaskStatus.RUNNING)

    @property
    def pending_count(self) -> int:
        """Number of tasks waiting to start."""
        return sum(1 for entry in self._tasks.values() if entry.task.status == TaskStatus.PENDING)

    async def submit(
        self,
        name: str,
        handler: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
    ) -> Task:
        """Submit an async *handler* for execution and return a :class:`Task`."""
        task = Task(name=name)
        async with self._capacity_condition:
            if self._shutdown:
                raise RuntimeError("pool is shut down")
            await self._ensure_capacity_locked()
            slot_index = self._select_slot_locked()
            entry = _TaskEntry(task=task, handler=handler, args=args, slot_index=slot_index)
            self._tasks[task.id] = entry
            self._slot_loads[slot_index] += 1
            self._pending_order.append(task.id)
            entry.future = asyncio.create_task(self._run(entry))
        return task

    async def wait(self, task_id: str, timeout: float | None = None) -> TaskResult:
        """Block until the task identified by *task_id* completes."""
        entry = self._tasks.get(task_id)
        if entry is None:
            raise KeyError(f"unknown task: {task_id}")
        assert entry.future is not None

        try:
            await asyncio.wait_for(asyncio.shield(entry.future), timeout=timeout)
        except TimeoutError:
            entry.future.cancel()
            try:
                await entry.future
            except asyncio.CancelledError:
                # Waiter cancellation should not cancel the tracked worker task.
                pass
            entry.task.status = TaskStatus.FAILED
            entry.events.append(error_event(task_id, message="task timed out"))
        except asyncio.CancelledError:
            if not entry.future.cancelled():
                # The CALLER cancelled their wait() — propagate so they know it ended.
                # asyncio.shield() above ensures entry.future keeps running.
                raise
            # The underlying worker task was cancelled by the pool itself (e.g.,
            # DROP_OLDEST eviction or graceful shutdown). Return the task result
            # (CANCELLED status) rather than propagating an unrelated cancellation.

        return self._build_result(entry)

    async def cancel(self, task_id: str) -> None:
        """Cancel a pending or running task."""
        entry = self._tasks.get(task_id)
        if entry is None:
            raise KeyError(f"unknown task: {task_id}")

        if entry.future is not None and not entry.future.done():
            entry.future.cancel()
            try:
                await entry.future
            except asyncio.CancelledError:
                # The caller requested cancellation; the task state is updated below.
                pass

        if entry.task.status in {TaskStatus.PENDING, TaskStatus.RUNNING}:
            entry.task.status = TaskStatus.CANCELLED

    async def shutdown(self, graceful: bool = True) -> None:
        """Shut down the pool, optionally waiting for in-flight tasks."""
        async with self._capacity_condition:
            self._shutdown = True
            self._capacity_condition.notify_all()

        in_flight = [
            entry.future for entry in self._tasks.values() if entry.future and not entry.future.done()
        ]

        if not in_flight:
            return

        if graceful:
            _, pending = await asyncio.wait(in_flight, timeout=self._config.graceful_timeout)
            for future in pending:
                future.cancel()
            if pending:
                await asyncio.wait(pending)
        else:
            for future in in_flight:
                future.cancel()
            await asyncio.wait(in_flight)

    async def _ensure_capacity_locked(self) -> None:
        if self._shutdown:
            raise RuntimeError("pool is shut down")
        if self._config.max_pending_tasks is None:
            return

        capacity = self._config.max_workers + self._config.max_pending_tasks
        while self._live_count_locked() >= capacity:
            if self._shutdown:
                raise RuntimeError("pool is shut down")
            if self._config.overflow_policy == OverflowPolicy.REJECT:
                raise PoolOverflowError("worker pool is at capacity")
            if (
                self._config.overflow_policy == OverflowPolicy.DROP_OLDEST
                and self._drop_oldest_pending_locked()
            ):
                return
            await self._capacity_condition.wait()
            if self._shutdown:
                raise RuntimeError("pool is shut down")

    def _live_count_locked(self) -> int:
        return sum(
            1
            for entry in self._tasks.values()
            if entry.task.status in {TaskStatus.PENDING, TaskStatus.RUNNING}
        )

    def _drop_oldest_pending_locked(self) -> bool:
        while self._pending_order:
            task_id = self._pending_order.popleft()
            entry = self._tasks.get(task_id)
            if (
                entry is None
                or entry.task.status != TaskStatus.PENDING
                or entry.queue_state != _QueueState.QUEUED
                or entry.future is None
            ):
                continue
            entry.task.status = TaskStatus.CANCELLED
            entry.queue_state = _QueueState.DONE
            entry.events.append(error_event(task_id, message="task dropped due to overflow"))
            entry.future.cancel()
            return True
        return False

    def _select_slot_locked(self) -> int:
        if self._config.dispatch_strategy == DispatchStrategy.LEAST_LOADED:
            return min(range(len(self._slot_loads)), key=self._slot_loads.__getitem__)
        slot_index = self._dispatch_counter % len(self._slot_loads)
        self._dispatch_counter += 1
        return slot_index

    async def _run(self, entry: _TaskEntry) -> None:
        semaphore = self._slot_semaphores[entry.slot_index]
        acquired = False
        try:
            await semaphore.acquire()
            acquired = True
            async with self._capacity_condition:
                entry.queue_state = _QueueState.ACQUIRING
                self._discard_pending_locked(entry.task.id)
                self._capacity_condition.notify_all()

            if entry.task.status == TaskStatus.CANCELLED:
                return

            entry.start_time = time.monotonic()
            async with self._capacity_condition:
                entry.queue_state = _QueueState.RUNNING
                entry.task.status = TaskStatus.RUNNING
            try:
                result = await self._execute_handler(entry)
            except asyncio.CancelledError:
                entry.task.status = TaskStatus.CANCELLED
                raise
            except Exception as exc:
                entry.task.status = TaskStatus.FAILED
                entry.events.append(error_event(entry.task.id, message=str(exc)))
            else:
                entry.task.status = TaskStatus.COMPLETED
                entry.events.append(complete_event(entry.task.id, data=result))
        finally:
            if acquired:
                semaphore.release()
            async with self._capacity_condition:
                entry.queue_state = _QueueState.DONE
                self._slot_loads[entry.slot_index] -= 1
                self._discard_pending_locked(entry.task.id)
                self._capacity_condition.notify_all()

    async def _execute_handler(self, entry: _TaskEntry) -> Any:
        if self._config.task_timeout is None:
            return await entry.handler(*entry.args)
        try:
            return await asyncio.wait_for(entry.handler(*entry.args), timeout=self._config.task_timeout)
        except TimeoutError as exc:
            raise RuntimeError("task timed out") from exc

    def _discard_pending_locked(self, task_id: str) -> None:
        self._pending_order = deque(pending_id for pending_id in self._pending_order if pending_id != task_id)

    def _build_result(self, entry: _TaskEntry) -> TaskResult:
        duration = time.monotonic() - entry.start_time if entry.start_time else 0.0
        result_data: Any = None
        error_msg: str | None = None

        for event in entry.events:
            if event.type == EventType.COMPLETE:
                result_data = event.data
            elif event.type == EventType.ERROR:
                error_msg = event.message or str(event.data)

        return TaskResult(
            task_id=entry.task.id,
            status=entry.task.status,
            result=result_data,
            error=error_msg,
            events=list(entry.events),
            duration=duration,
        )
