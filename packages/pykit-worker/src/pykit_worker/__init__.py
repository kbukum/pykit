"""pykit-worker — Async task pool with typed events."""

from __future__ import annotations

from pykit_worker.event import Event, EventType
from pykit_worker.pool import PoolConfig, WorkerPool
from pykit_worker.task import Task, TaskResult, TaskStatus
from pykit_worker.ticker import TickerWorker

__all__ = [
    "Event",
    "EventType",
    "PoolConfig",
    "Task",
    "TaskResult",
    "TaskStatus",
    "TickerWorker",
    "WorkerPool",
]
