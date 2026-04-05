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
