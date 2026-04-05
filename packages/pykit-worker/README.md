# pykit-worker

Async task pool with typed events, concurrency control, timeout management, and structured task lifecycle tracking.

## Installation

```bash
pip install pykit-worker
# or
uv add pykit-worker
```

## Quick Start

```python
from pykit_worker import WorkerPool, PoolConfig, TaskStatus, EventType

# Create a pool with concurrency limit
pool = WorkerPool(PoolConfig(max_workers=5, task_timeout=60.0))

# Define an async task handler
async def process_image(path: str) -> dict:
    # ... processing logic ...
    return {"width": 1920, "height": 1080}

# Submit and wait for result
task = await pool.submit("resize-photo", process_image, "/uploads/photo.jpg")
result = await pool.wait(task.id, timeout=30.0)

if result.status == TaskStatus.COMPLETED:
    print(f"Done in {result.duration:.2f}s: {result.result}")
else:
    print(f"Failed: {result.error}")

# Check pool state
print(pool.active_count)   # currently running tasks
print(pool.pending_count)  # tasks waiting to start

# Cancel a task
await pool.cancel(task.id)

# Graceful shutdown
await pool.shutdown(graceful=True)
```

## Key Components

- **WorkerPool** — Async task pool with semaphore-based concurrency limiting, event collection, and graceful shutdown
- **PoolConfig** — Configuration: `max_workers` (default 10), `task_timeout`, `graceful_timeout` (default 30s)
- **Task** — Lightweight handle with `name`, `id` (UUID), `status`, and `created_at`
- **TaskResult** — Outcome with `task_id`, `status`, `result`, `error`, `events`, and `duration`
- **TaskStatus** — Lifecycle enum: `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`
- **Event** — Typed event emitted during execution with `type`, `task_id`, `data`, `timestamp`, `message`
- **EventType** — Event classification: `PROGRESS`, `PARTIAL`, `COMPLETE`, `ERROR`, `LOG`

## Dependencies

- `pykit-errors`

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
