# pykit-worker

Run background jobs with bounded concurrency, typed lifecycle events, queue policies, and graceful shutdown.

## Installation

```bash
pip install pykit-worker
# or
uv add pykit-worker
```

## Quick start

```python
from pykit_worker import PoolConfig, TaskStatus, WorkerPool

pool = WorkerPool(PoolConfig(max_workers=5, task_timeout=60.0))

async def process_image(path: str) -> dict:
    return {"width": 1920, "height": 1080}

task = await pool.submit("resize-photo", process_image, "/uploads/photo.jpg")
result = await pool.wait(task.id, timeout=30.0)

if result.status == TaskStatus.COMPLETED:
    print(result.result)
else:
    print(result.error)

print(pool.active_count)
print(pool.pending_count)

await pool.cancel(task.id)
await pool.shutdown(graceful=True)
```

## Core APIs

- **`WorkerPool`** limits concurrency, queues pending tasks, and collects typed events.
- **`PoolConfig`** configures `max_workers`, `task_timeout`, `graceful_timeout`, `max_pending_tasks`, `overflow_policy`, and `dispatch_strategy`.
- **`Task`**, **`TaskResult`**, and **`TaskStatus`** model task lifecycle state.
- **`Event`** and **`EventType`** capture progress, partial output, completion, errors, and logs.
- **`OverflowPolicy`** and **`DispatchStrategy`** let callers control queue behavior.
- **`TickerWorker`** runs a named handler on a fixed interval with health reporting.

## Dependencies

- `pykit-errors`
- `pykit-component`

## See also

- [Main pykit README](../../../README.md)
- [tests/](tests/)
