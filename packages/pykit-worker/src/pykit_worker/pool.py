"""Async worker pool with concurrency control and event collection."""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

from pykit_worker.event import Event, EventType, complete_event, error_event
from pykit_worker.task import Task, TaskResult, TaskStatus


@dataclass
class PoolConfig:
    """Configuration for :class:`WorkerPool`."""

    max_workers: int = 10
    task_timeout: float | None = None
    graceful_timeout: float = 30.0


# Internal bookkeeping for an in-flight task.
@dataclass
class _TaskEntry:
    task: Task
    handler: Callable[..., Coroutine[Any, Any, Any]]
    args: tuple[Any, ...]
    future: asyncio.Task[Any] | None = None
    events: list[Event] = field(default_factory=list)
    start_time: float = 0.0


class WorkerPool:
    """Async task pool with concurrency limiting and event collection.

    Uses :class:`asyncio.Semaphore` to cap the number of concurrently
    running handlers at ``config.max_workers``.
    """

    def __init__(self, config: PoolConfig | None = None) -> None:
        self._config = config or PoolConfig()
        self._semaphore = asyncio.Semaphore(self._config.max_workers)
        self._tasks: dict[str, _TaskEntry] = {}
        self._shutdown = False

    # -- public helpers ------------------------------------------------------

    @property
    def active_count(self) -> int:
        """Number of tasks currently running."""
        return sum(1 for e in self._tasks.values() if e.task.status == TaskStatus.RUNNING)

    @property
    def pending_count(self) -> int:
        """Number of tasks waiting to start."""
        return sum(1 for e in self._tasks.values() if e.task.status == TaskStatus.PENDING)

    # -- core API ------------------------------------------------------------

    async def submit(
        self,
        name: str,
        handler: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
    ) -> Task:
        """Submit an async *handler* for execution and return a :class:`Task`."""
        if self._shutdown:
            raise RuntimeError("pool is shut down")

        task = Task(name=name)
        entry = _TaskEntry(task=task, handler=handler, args=args)
        self._tasks[task.id] = entry

        entry.future = asyncio.create_task(self._run(entry))
        return task

    async def wait(self, task_id: str, timeout: float | None = None) -> TaskResult:
        """Block until the task identified by *task_id* completes."""
        entry = self._tasks.get(task_id)
        if entry is None:
            raise KeyError(f"unknown task: {task_id}")

        effective_timeout = timeout if timeout is not None else self._config.task_timeout
        assert entry.future is not None

        try:
            await asyncio.wait_for(
                asyncio.shield(entry.future),
                timeout=effective_timeout,
            )
        except TimeoutError:
            entry.future.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await entry.future
            entry.task.status = TaskStatus.FAILED
            duration = time.monotonic() - entry.start_time if entry.start_time else 0.0
            entry.events.append(error_event(task_id, message="task timed out"))
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error="task timed out",
                events=list(entry.events),
                duration=duration,
            )

        return self._build_result(entry)

    async def cancel(self, task_id: str) -> None:
        """Cancel a pending or running task."""
        entry = self._tasks.get(task_id)
        if entry is None:
            raise KeyError(f"unknown task: {task_id}")

        if entry.future is not None and not entry.future.done():
            entry.future.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await entry.future

        if entry.task.status in {TaskStatus.PENDING, TaskStatus.RUNNING}:
            entry.task.status = TaskStatus.CANCELLED

    async def shutdown(self, graceful: bool = True) -> None:
        """Shut down the pool, optionally waiting for in-flight tasks."""
        self._shutdown = True

        in_flight = [e.future for e in self._tasks.values() if e.future is not None and not e.future.done()]

        if not in_flight:
            return

        if graceful:
            _, pending = await asyncio.wait(
                in_flight,
                timeout=self._config.graceful_timeout,
            )
            for fut in pending:
                fut.cancel()
            if pending:
                await asyncio.wait(pending)
        else:
            for fut in in_flight:
                fut.cancel()
            await asyncio.wait(in_flight)

    # -- internals -----------------------------------------------------------

    async def _run(self, entry: _TaskEntry) -> None:
        """Acquire the semaphore, execute the handler, record the outcome."""
        await self._semaphore.acquire()
        entry.start_time = time.monotonic()
        entry.task.status = TaskStatus.RUNNING
        try:
            result = await entry.handler(*entry.args)
            entry.task.status = TaskStatus.COMPLETED
            entry.events.append(complete_event(entry.task.id, data=result))
        except asyncio.CancelledError:
            if entry.task.status == TaskStatus.RUNNING:
                entry.task.status = TaskStatus.CANCELLED
            raise
        except Exception as exc:
            entry.task.status = TaskStatus.FAILED
            entry.events.append(
                error_event(entry.task.id, message=str(exc)),
            )
        finally:
            self._semaphore.release()

    def _build_result(self, entry: _TaskEntry) -> TaskResult:
        duration = time.monotonic() - entry.start_time if entry.start_time else 0.0

        result_data: Any = None
        error_msg: str | None = None

        for ev in entry.events:
            if ev.type == EventType.COMPLETE:
                result_data = ev.data
            elif ev.type == EventType.ERROR:
                error_msg = ev.message or str(ev.data)

        return TaskResult(
            task_id=entry.task.id,
            status=entry.task.status,
            result=result_data,
            error=error_msg,
            events=list(entry.events),
            duration=duration,
        )
