"""Tests for as_tool — wrapping a DAG as a RequestResponse provider."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from pykit_dag import Engine, Graph
from pykit_dag.as_tool import DagTool, ToolConfig, as_tool

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


@dataclass
class FuncNode:
    """A simple node that delegates to a callable."""

    name: str
    dependencies: list[str] = field(default_factory=list)
    _fn: Any = None

    async def execute(self, inputs: dict[str, Any]) -> Any:
        if self._fn is None:
            return None
        return await self._fn(inputs)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_as_tool_basic() -> None:
    """Create a 2-node DAG (input → transform), wrap with as_tool, verify output."""

    async def input_node(inputs: dict[str, Any]) -> int:
        return inputs["value"]

    async def transform_node(inputs: dict[str, Any]) -> int:
        return inputs["input_node"] * 2

    graph = Graph()
    graph.add_node(FuncNode("input_node", [], input_node))
    graph.add_node(FuncNode("transform_node", ["input_node"], transform_node))

    engine = Engine()
    config: ToolConfig[dict[str, int], int] = ToolConfig(
        name="doubler",
        input_fn=lambda inp: {"value": inp["value"]},
        output_fn=lambda result: result.states["transform_node"].result,
    )

    tool = as_tool(engine, graph, config)
    output = await tool.execute({"value": 5})
    assert output == 10


@pytest.mark.asyncio
async def test_as_tool_name() -> None:
    """Verify .name returns config name."""
    graph = Graph()
    engine = Engine()
    config: ToolConfig[str, str] = ToolConfig(
        name="my-tool",
        input_fn=lambda inp: {},
        output_fn=lambda result: "",
    )
    tool = as_tool(engine, graph, config)
    assert tool.name == "my-tool"


@pytest.mark.asyncio
async def test_as_tool_is_available() -> None:
    """Verify is_available returns True."""
    graph = Graph()
    engine = Engine()
    config: ToolConfig[str, str] = ToolConfig(
        name="avail-check",
        input_fn=lambda inp: {},
        output_fn=lambda result: "",
    )
    tool = as_tool(engine, graph, config)
    assert await tool.is_available() is True


@pytest.mark.asyncio
async def test_as_tool_failure_propagates() -> None:
    """DAG with a failing node — verify error propagates."""

    async def failing_node(inputs: dict[str, Any]) -> None:
        msg = "node exploded"
        raise ValueError(msg)

    graph = Graph()
    graph.add_node(FuncNode("boom", [], failing_node))

    engine = Engine()
    config: ToolConfig[dict[str, Any], str] = ToolConfig(
        name="fail-tool",
        input_fn=lambda inp: {},
        output_fn=lambda result: result.states["boom"].result,
    )

    tool = as_tool(engine, graph, config)
    with pytest.raises(ValueError, match="node exploded"):
        await tool.execute({})


@pytest.mark.asyncio
async def test_as_tool_satisfies_protocol() -> None:
    """Verify DagTool structurally matches RequestResponse."""
    from pykit_provider import RequestResponse

    graph = Graph()
    engine = Engine()
    config: ToolConfig[str, str] = ToolConfig(
        name="proto-check",
        input_fn=lambda inp: {},
        output_fn=lambda result: "",
    )
    tool = DagTool(engine, graph, config)
    assert isinstance(tool, RequestResponse)
