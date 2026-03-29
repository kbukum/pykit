"""DAG execution engine."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pykit_dag.graph import Graph
from pykit_dag.node import NodeState, NodeStatus


class FailurePolicy(StrEnum):
    """How the engine handles node failures."""

    FAIL_FAST = "fail_fast"
    CONTINUE = "continue"
    SKIP_DEPENDENTS = "skip_dependents"


@dataclass
class EngineConfig:
    """Configuration for the DAG engine."""

    max_concurrency: int = 10
    failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST
    timeout: float | None = None


@dataclass
class ExecutionResult:
    """Result of executing a DAG."""

    states: dict[str, NodeState] = field(default_factory=dict)
    duration: float = 0.0
    success: bool = True


class Engine:
    """Executes a DAG in topological order with concurrency control."""

    def __init__(self, config: EngineConfig | None = None) -> None:
        self._config = config or EngineConfig()

    async def execute(self, graph: Graph, inputs: dict[str, Any] | None = None) -> ExecutionResult:
        """Execute all nodes in the graph respecting dependencies."""
        inputs = inputs or {}
        result = ExecutionResult()
        start = time.monotonic()

        levels = graph.topological_sort()
        nodes = graph.nodes
        semaphore = asyncio.Semaphore(self._config.max_concurrency)
        failed_nodes: set[str] = set()
        skipped_nodes: set[str] = set()

        try:
            if self._config.timeout is not None:
                await asyncio.wait_for(
                    self._execute_levels(
                        levels, nodes, inputs, result, semaphore, failed_nodes, skipped_nodes
                    ),
                    timeout=self._config.timeout,
                )
            else:
                await self._execute_levels(
                    levels, nodes, inputs, result, semaphore, failed_nodes, skipped_nodes
                )
        except TimeoutError:
            # Mark remaining pending nodes as failed with timeout
            for name in nodes:
                if name not in result.states or result.states[name].status == NodeStatus.PENDING:
                    result.states[name] = NodeState(
                        status=NodeStatus.FAILED,
                        error=TimeoutError("execution timed out"),
                    )
            result.success = False

        result.duration = time.monotonic() - start
        result.success = result.success and all(
            s.status == NodeStatus.COMPLETED for s in result.states.values()
        )
        return result

    async def _execute_levels(
        self,
        levels: list[list[str]],
        nodes: dict[str, Any],
        inputs: dict[str, Any],
        result: ExecutionResult,
        semaphore: asyncio.Semaphore,
        failed_nodes: set[str],
        skipped_nodes: set[str],
    ) -> None:
        abort = False

        for level in levels:
            if abort:
                for name in level:
                    result.states[name] = NodeState(status=NodeStatus.SKIPPED)
                    skipped_nodes.add(name)
                continue

            tasks = []
            for name in level:
                if name in skipped_nodes:
                    continue
                # Check if any dependency failed/skipped
                node = nodes[name]
                should_skip = self._should_skip(node, failed_nodes, skipped_nodes)
                if should_skip:
                    result.states[name] = NodeState(status=NodeStatus.SKIPPED)
                    skipped_nodes.add(name)
                    continue
                tasks.append(self._run_node(name, node, inputs, result, semaphore))

            if tasks:
                await asyncio.gather(*tasks)

            # Check for failures after this level
            for name in level:
                state = result.states.get(name)
                if state and state.status == NodeStatus.FAILED:
                    failed_nodes.add(name)
                    if self._config.failure_policy == FailurePolicy.FAIL_FAST:
                        abort = True

    def _should_skip(self, node: Any, failed_nodes: set[str], skipped_nodes: set[str]) -> bool:
        """Determine if a node should be skipped based on failure policy."""
        if self._config.failure_policy == FailurePolicy.SKIP_DEPENDENTS:
            for dep in node.dependencies:
                if dep in failed_nodes or dep in skipped_nodes:
                    return True
        return False

    async def _run_node(
        self,
        name: str,
        node: Any,
        inputs: dict[str, Any],
        result: ExecutionResult,
        semaphore: asyncio.Semaphore,
    ) -> None:
        async with semaphore:
            state = NodeState(status=NodeStatus.RUNNING)
            result.states[name] = state
            start = time.monotonic()
            try:
                # Gather inputs from dependencies
                node_inputs = dict(inputs)
                for dep in node.dependencies:
                    dep_state = result.states.get(dep)
                    if dep_state and dep_state.status == NodeStatus.COMPLETED:
                        node_inputs[dep] = dep_state.result

                output = await node.execute(node_inputs)
                state.status = NodeStatus.COMPLETED
                state.result = output
            except Exception as exc:
                state.status = NodeStatus.FAILED
                state.error = exc
            finally:
                state.duration = time.monotonic() - start
