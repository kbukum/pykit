"""Wrap a DAG execution as a RequestResponse provider."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pykit_dag.engine import Engine, ExecutionResult
from pykit_dag.graph import Graph


@dataclass(frozen=True)
class ToolConfig[In, Out]:
    """Configuration for wrapping a DAG as a provider."""

    name: str
    input_fn: Callable[[In], dict[str, Any]]
    output_fn: Callable[[ExecutionResult], Out]


class DagTool[In, Out]:
    """Wraps a DAG execution as a RequestResponse provider.

    Satisfies the RequestResponse protocol (name, is_available, execute)
    without importing pykit-provider — uses structural subtyping.
    """

    def __init__(self, engine: Engine, graph: Graph, config: ToolConfig[In, Out]) -> None:
        self._engine = engine
        self._graph = graph
        self._config = config

    @property
    def name(self) -> str:
        return self._config.name

    async def is_available(self) -> bool:
        return True

    async def execute(self, input: In) -> Out:
        inputs = self._config.input_fn(input)
        result = await self._engine.execute(self._graph, inputs)
        if not result.success:
            for state in result.states.values():
                if state.error is not None:
                    raise state.error
            msg = "DAG execution failed"
            raise RuntimeError(msg)
        return self._config.output_fn(result)


def as_tool[In, Out](engine: Engine, graph: Graph, config: ToolConfig[In, Out]) -> DagTool[In, Out]:
    """Wrap a DAG execution as a RequestResponse provider."""
    return DagTool(engine, graph, config)
