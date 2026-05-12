# pykit-stateful

Stateful accumulator with configurable flush triggers, FIFO eviction, and pluggable storage backends.

## Installation

```bash
pip install pykit-stateful
# or
uv add pykit-stateful
```

## Quick Start

```python
from pykit_stateful import (
    Accumulator, AccumulatorConfig,
    SizeTrigger, ByteSizeTrigger, TimeTrigger,
    MemoryStore,
)

# Flush callback
async def on_flush(items: list[dict]) -> None:
    print(f"Flushing {len(items)} items")

# Accumulator with size and time triggers
acc = Accumulator(
    config=AccumulatorConfig(max_size=1000, flush_size=100),
    on_flush=on_flush,
    triggers=[SizeTrigger(threshold=50), TimeTrigger(interval=10.0)],
)

await acc.push({"event": "click", "user": "alice"})
await acc.push({"event": "view", "user": "bob"})
print(acc.count)  # 2

# Manual flush
await acc.flush()

# Pluggable key-value store
store = MemoryStore[str]()
await store.set("key", "value")
val = await store.get("key")  # "value"
```

## Key Components

- **Accumulator[V]** — Push-based buffer with automatic flush triggers and FIFO eviction when max_size is reached
- **AccumulatorConfig** — Configuration: `max_size`, `flush_size`, `ttl`, `flush_interval`
- **FlushTrigger** — Protocol for custom flush conditions (`should_flush(items) → bool`)
- **SizeTrigger** — Flush when item count reaches threshold
- **ByteSizeTrigger** — Flush when total byte size reaches threshold (custom measurer support)
- **TimeTrigger** — Flush after elapsed time interval since last flush
- **Store[V]** — Async key-value storage protocol (`get`, `set`, `delete`, `keys`)
- **MemoryStore[V]** — In-memory dict-based Store implementation

## Dependencies

- `pykit-errors`

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
