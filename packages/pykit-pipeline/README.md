# pykit-pipeline

Composable, pull-based async data pipelines with lazy evaluation and chainable operators.

## Installation

```bash
pip install pykit-pipeline
# or
uv add pykit-pipeline
```

## Quick Start

```python
from pykit_pipeline import Pipeline, collect, concat, reduce, drain

# Build a lazy pipeline — no work until a terminal is called
results = await collect(
    Pipeline.from_list([1, 2, 3, 4, 5])
    .map(lambda x: x * 2)
    .filter(lambda x: x > 4)
    .tap(lambda x: print(f"passing: {x}"))
)
# prints: passing: 6, passing: 8, passing: 10
# results: [6, 8, 10]

# Concatenate multiple pipelines
combined = concat(Pipeline.from_list([1, 2]), Pipeline.from_list([3, 4]))
print(await collect(combined))  # [1, 2, 3, 4]

# Reduce to a single value
total = await collect(reduce(Pipeline.from_list([1, 2, 3]), 0, lambda acc, x: acc + x))
# total: [6]
```

## Operator reference

| Operator | pykit API | Notes |
|---|---|---|
| map | `Pipeline.map(fn)` | Synchronous item transform. |
| filter | `Pipeline.filter(predicate)` | Keeps matching values. |
| batch | `Pipeline.batch(size)` | Fixed-size batches, final partial batch emitted. |
| window | `Pipeline.tumbling_window(size)` | Non-overlapping count window. |
| sliding | `Pipeline.sliding_window(size, step=1)` | Overlapping count window. |
| fan_out | `Pipeline.fan_out(*fns)` | Applies multiple sync/async functions per item. |
| parallel | `Pipeline.parallel(concurrency, fn)` | Concurrent unordered map. |
| merge | `Pipeline.merge(*others)` | Concurrent unordered merge. |
| partition | `Pipeline.partition(predicate)` | Splits into matching and non-matching pipelines. |
| throttle | `Pipeline.throttle(interval)` | Drops values faster than interval. |
| debounce | `Pipeline.debounce(interval)` | Emits latest value after quiet period. |
| distinct | `Pipeline.distinct()` | Emits first occurrence of each value. |
| take | `Pipeline.take(n)` | Emits at most `n` values. |
| skip | `Pipeline.skip(n)` | Skips first `n` values. |
| buffer | `Pipeline.buffer(size)` | Inserts bounded async producer buffer. |

## Key Components

- **Pipeline[T]** — Lazy, pull-based async data pipeline with chainable operators (`map`, `filter`, `tap`, `flat_map`)
- **PipelineIterator[T]** — Abstract async iterator base for pull-based sequential access
- **collect()** — Terminal: pulls all values into a list
- **drain()** — Terminal: pulls all values and sends each to a sync or async sink function
- **for_each()** — Terminal: calls a function for each value
- **concat()** — Combinator: joins multiple pipelines sequentially
- **reduce()** — Combinator: accumulates values into a single result

## Dependencies

None — zero external dependencies.

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
