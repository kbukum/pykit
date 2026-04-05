# pykit-dag

Async DAG execution engine with topological sorting, concurrent node execution, and configurable failure policies.

## Installation

```bash
pip install pykit-dag
# or
uv add pykit-dag
```

## Quick Start

```python
import asyncio
from pykit_dag import Engine, EngineConfig, FailurePolicy, Graph, Node

class FetchData:
    @property
    def name(self) -> str: return "fetch"
    @property
    def dependencies(self) -> list[str]: return []
    async def execute(self, inputs: dict) -> dict:
        return {"records": [1, 2, 3]}

class Transform:
    @property
    def name(self) -> str: return "transform"
    @property
    def dependencies(self) -> list[str]: return ["fetch"]
    async def execute(self, inputs: dict) -> list:
        return [x * 2 for x in inputs["fetch"]["records"]]

graph = Graph()
graph.add_node(FetchData())
graph.add_node(Transform())
graph.validate()  # checks for cycles and missing deps

config = EngineConfig(max_concurrency=4, failure_policy=FailurePolicy.SKIP_DEPENDENTS)
result = asyncio.run(Engine(config).execute(graph))
print(result.success, result.duration)
```

## Key Components

- **Node** — Runtime-checkable protocol requiring `name`, `dependencies`, and `async execute(inputs)` — node results are automatically passed as inputs to dependents
- **Graph** — DAG container with `add_node()`, `add_edge()`, `validate()` (cycle detection via DFS), and `topological_sort()` (Kahn's algorithm, groups nodes by execution level)
- **Engine** — Executes nodes in topological order with bounded concurrency via semaphore; passes dependency outputs downstream
- **EngineConfig** — Configuration with `max_concurrency` (default 10), `failure_policy`, and optional `timeout`
- **FailurePolicy** — StrEnum: `FAIL_FAST` (stop on first error), `CONTINUE` (run independent nodes), `SKIP_DEPENDENTS` (skip nodes depending on failed ones)
- **ExecutionResult** — Result with `states` (per-node `NodeState`), `duration`, and `success` flag
- **NodeStatus** — StrEnum: `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `SKIPPED`
- **NodeState** — Tracks `status`, `result`, `error`, and `duration` per node
- **CycleError / MissingNodeError** — Validation errors extending `AppError`

## Dependencies

- `pykit-errors` — Error handling (`AppError` subclasses for cycle and missing node errors)

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
