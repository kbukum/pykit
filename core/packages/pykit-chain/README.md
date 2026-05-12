# pykit-chain

Sequential chain execution with per-step progress, cancellation, and cleanup.

Mirrors [gokit/chain](https://github.com/skillsenselab/gokit/tree/main/chain) (Go) and [rskit-chain](https://github.com/skillsenselab/rskit/tree/main/crates/rskit-chain) (Rust).

## When to Use

| Pattern | Use Case |
|---------|----------|
| **pykit-chain** | Sequential steps where each output feeds the next (media processing pipeline, ETL) |
| **pykit-dag** | Parallel tasks with dependencies (build graph, data pipeline) |
| **pykit-pipeline** | Stream processing with operators (log processing, event streaming) |

## Quick Start

```python
from dataclasses import dataclass
from typing import Any
from pykit_chain import ChainBuilder, StepProgress

@dataclass
class DoubleOp:
    id: str = "double"
    name: str = "Double"

    async def execute(self, input: Any, progress) -> Any:
        result = input * 2
        progress(100, f"doubled to {result}")
        return result

    async def cleanup(self, output: Any) -> None:
        pass

chain = ChainBuilder().step(DoubleOp()).step(DoubleOp()).build()
result = await chain.execute(5)  # 5 → 10 → 20
assert result.final_output == 20
```

## Features

- **Sequential execution** — each step receives the previous step's output
- **Per-step progress** — callback with step index, percent, and message
- **Cancellation** — pass an `asyncio.Event`; remaining steps are marked cancelled
- **Cleanup on failure** — completed steps' `cleanup()` called in reverse order
- **Continue after failure** — optionally run remaining steps even after a failure
- **Fluent builder** — `ChainBuilder().step(a).step(b).build()`
