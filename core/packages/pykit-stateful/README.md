# pykit-stateful

Buffer, flush, and manage stateful streams with configurable triggers and pluggable stores.

## Installation

```bash
pip install pykit-stateful
# or
uv add pykit-stateful
```

## Quick start

```python
from pykit_stateful import (
    Accumulator,
    AccumulatorConfig,
    MemoryStore,
    SizeTrigger,
    TimeTrigger,
)

async def on_flush(items: list[dict]) -> None:
    print(f"Flushing {len(items)} items")

acc = Accumulator(
    config=AccumulatorConfig(max_size=1000, flush_size=100),
    on_flush=on_flush,
    triggers=[SizeTrigger(threshold=50), TimeTrigger(interval=10.0)],
)

await acc.push({"event": "click", "user": "alice"})
await acc.push({"event": "view", "user": "bob"})
print(acc.count)

await acc.flush()

store = MemoryStore[str]()
await store.set("key", "value")
value = await store.get("key")
```

## Core APIs

- **`Accumulator[V]`** buffers items, flushes on demand or by trigger, and evicts in FIFO order when `max_size` is reached.
- **`AccumulatorConfig`** configures `max_size`, `flush_size`, `ttl`, and `flush_interval`.
- **`SizeTrigger`**, **`ByteSizeTrigger`**, and **`TimeTrigger`** cover common flush strategies.
- **`Store[V]`** defines the async key-value store contract.
- **`MemoryStore[V]`** is the default in-memory store.
- **`Manager`** coordinates multiple accumulators by key and adds cleanup helpers.

## See also

- [Main pykit README](../../../README.md)
- [tests/](tests/)
