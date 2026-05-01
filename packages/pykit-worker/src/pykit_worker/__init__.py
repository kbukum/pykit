"""pykit-worker — Async task pool with typed events."""

from __future__ import annotations

from pykit_worker.event import Event, EventType
from pykit_worker.pool import DispatchStrategy, OverflowPolicy, PoolConfig, PoolOverflowError, WorkerPool
from pykit_worker.task import Task, TaskResult, TaskStatus
from pykit_worker.ticker import TickerWorker

__all__ = [
    "Event",
    "EventType",
    "DispatchStrategy",
    "OverflowPolicy",
    "PoolConfig",
    "PoolOverflowError",
    "Task",
    "TaskResult",
    "TaskStatus",
    "TickerWorker",
    "WorkerPool",
]
