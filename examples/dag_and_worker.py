"""Example: DAG execution and worker pool.

Demonstrates:
- Building a DAG with typed nodes and dependencies
- Executing nodes in topological order via the Engine
- Processing concurrent tasks with WorkerPool
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from pykit_dag import Engine, EngineConfig, FailurePolicy, Graph
from pykit_worker import PoolConfig, WorkerPool

# ---------------------------------------------------------------------------
# 1. DAG — build and execute
# ---------------------------------------------------------------------------


@dataclass
class SimpleNode:
    """Concrete node that satisfies the pykit_dag.Node protocol."""

    _name: str
    _deps: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self._name

    @property
    def dependencies(self) -> list[str]:
        return self._deps

    async def execute(self, inputs: dict[str, Any]) -> Any:
        # Simulate some work
        await asyncio.sleep(0.02)
        result = f"{self._name}-done"
        print(f"  [{self._name}] executed (inputs={list(inputs.keys())}) → {result}")
        return result


async def demo_dag() -> None:
    """Build a diamond-shaped DAG and run it."""
    print("=== DAG Execution ===")

    #   fetch
    #   /   \
    # parse  validate
    #   \   /
    #   merge

    graph = Graph()
    graph.add_node(SimpleNode("fetch"))
    graph.add_node(SimpleNode("parse", ["fetch"]))
    graph.add_node(SimpleNode("validate", ["fetch"]))
    graph.add_node(SimpleNode("merge", ["parse", "validate"]))

    graph.validate()
    levels = graph.topological_sort()
    print(f"  Topological levels: {levels}")

    engine = Engine(EngineConfig(max_concurrency=4, failure_policy=FailurePolicy.FAIL_FAST))
    result = await engine.execute(graph)

    print(f"  Success: {result.success}, Duration: {result.duration:.3f}s")
    for name, state in result.states.items():
        print(f"    {name}: {state.status} → {state.result}")


# ---------------------------------------------------------------------------
# 2. Worker Pool — concurrent task processing
# ---------------------------------------------------------------------------


async def demo_worker_pool() -> None:
    """Submit tasks and wait for results."""
    print("\n=== Worker Pool ===")

    pool = WorkerPool(PoolConfig(max_workers=3))

    async def compute(n: int) -> int:
        await asyncio.sleep(0.05)
        return n * n

    # Submit several tasks
    tasks = []
    for i in range(5):
        task = await pool.submit(f"square-{i}", compute, i)
        tasks.append(task)
        print(f"  Submitted: {task.name} (id={task.id[:8]}…)")

    # Collect results
    for task in tasks:
        result = await pool.wait(task.id)
        print(f"  {task.name}: status={result.status}, result={result.result}")

    await pool.shutdown()
    print("  Pool shut down.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    await demo_dag()
    await demo_worker_pool()


if __name__ == "__main__":
    asyncio.run(main())
