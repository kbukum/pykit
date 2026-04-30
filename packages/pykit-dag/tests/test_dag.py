# mypy: ignore-errors
"""Comprehensive tests for pykit-dag."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest

from pykit_dag import Engine, EngineConfig, ExecutionResult, FailurePolicy, Graph, Node, NodeState, NodeStatus
from pykit_dag.graph import CycleError, MissingNodeError

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


@dataclass
class SimpleNode:
    """A basic node for testing."""

    name: str
    dependencies: list[str] = field(default_factory=list)
    _return_value: Any = None
    _side_effect: Exception | None = None
    _delay: float = 0.0

    async def execute(self, inputs: dict[str, Any]) -> Any:
        if self._delay > 0:
            await asyncio.sleep(self._delay)
        if self._side_effect is not None:
            raise self._side_effect
        return self._return_value


@dataclass
class AdderNode:
    """Node that sums values from its dependencies."""

    name: str
    dependencies: list[str] = field(default_factory=list)

    async def execute(self, inputs: dict[str, Any]) -> Any:
        total = 0
        for dep in self.dependencies:
            if dep in inputs:
                total += inputs[dep]
        return total


# ---------------------------------------------------------------------------
# Node protocol
# ---------------------------------------------------------------------------


class TestNodeProtocol:
    def test_simple_node_is_node(self) -> None:
        node = SimpleNode(name="a")
        assert isinstance(node, Node)

    def test_adder_node_is_node(self) -> None:
        node = AdderNode(name="add")
        assert isinstance(node, Node)


# ---------------------------------------------------------------------------
# NodeStatus / NodeState
# ---------------------------------------------------------------------------


class TestNodeStatus:
    def test_values(self) -> None:
        assert NodeStatus.PENDING == "pending"
        assert NodeStatus.RUNNING == "running"
        assert NodeStatus.COMPLETED == "completed"
        assert NodeStatus.FAILED == "failed"
        assert NodeStatus.SKIPPED == "skipped"


class TestNodeState:
    def test_defaults(self) -> None:
        state = NodeState()
        assert state.status == NodeStatus.PENDING
        assert state.result is None
        assert state.error is None
        assert state.duration == 0.0


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------


class TestGraph:
    def test_add_node(self) -> None:
        g = Graph()
        g.add_node(SimpleNode(name="a"))
        assert "a" in g.nodes

    def test_add_edge(self) -> None:
        g = Graph()
        g.add_node(SimpleNode(name="a"))
        g.add_node(SimpleNode(name="b"))
        g.add_edge("a", "b")
        g.validate()

    def test_add_edge_missing_node(self) -> None:
        g = Graph()
        g.add_node(SimpleNode(name="a"))
        with pytest.raises(MissingNodeError):
            g.add_edge("a", "missing")

    def test_cycle_detection_direct(self) -> None:
        g = Graph()
        g.add_node(SimpleNode(name="a"))
        g.add_node(SimpleNode(name="b"))
        g.add_edge("a", "b")
        g.add_edge("b", "a")
        with pytest.raises(CycleError):
            g.validate()

    def test_cycle_detection_indirect(self) -> None:
        g = Graph()
        g.add_node(SimpleNode(name="a"))
        g.add_node(SimpleNode(name="b"))
        g.add_node(SimpleNode(name="c"))
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_edge("c", "a")
        with pytest.raises(CycleError):
            g.topological_sort()

    def test_missing_dependency_in_validate(self) -> None:
        g = Graph()
        g.add_node(SimpleNode(name="a", dependencies=["nonexistent"]))
        with pytest.raises(MissingNodeError):
            g.validate()

    def test_topological_sort_linear(self) -> None:
        g = Graph()
        g.add_node(SimpleNode(name="a"))
        g.add_node(SimpleNode(name="b"))
        g.add_node(SimpleNode(name="c"))
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        levels = g.topological_sort()
        assert levels == [["a"], ["b"], ["c"]]

    def test_topological_sort_parallel(self) -> None:
        g = Graph()
        g.add_node(SimpleNode(name="a"))
        g.add_node(SimpleNode(name="b"))
        g.add_node(SimpleNode(name="c"))
        levels = g.topological_sort()
        # All independent → single level
        assert levels == [["a", "b", "c"]]

    def test_topological_sort_diamond(self) -> None:
        g = Graph()
        g.add_node(SimpleNode(name="a"))
        g.add_node(SimpleNode(name="b"))
        g.add_node(SimpleNode(name="c"))
        g.add_node(SimpleNode(name="d"))
        g.add_edge("a", "b")
        g.add_edge("a", "c")
        g.add_edge("b", "d")
        g.add_edge("c", "d")
        levels = g.topological_sort()
        assert levels == [["a"], ["b", "c"], ["d"]]

    def test_empty_graph(self) -> None:
        g = Graph()
        levels = g.topological_sort()
        assert levels == []

    def test_topological_sort_with_dependencies(self) -> None:
        """Dependencies declared on nodes (not just explicit edges) are respected."""
        g = Graph()
        g.add_node(SimpleNode(name="a"))
        g.add_node(SimpleNode(name="b", dependencies=["a"]))
        levels = g.topological_sort()
        assert levels == [["a"], ["b"]]


# ---------------------------------------------------------------------------
# Engine — simple linear DAG
# ---------------------------------------------------------------------------


class TestEngineLinear:
    @pytest.mark.asyncio
    async def test_linear_execution(self) -> None:
        g = Graph()
        g.add_node(SimpleNode(name="a", _return_value=1))
        g.add_node(SimpleNode(name="b", dependencies=["a"], _return_value=2))
        g.add_node(SimpleNode(name="c", dependencies=["b"], _return_value=3))

        result = await Engine().execute(g)

        assert result.success
        assert result.states["a"].status == NodeStatus.COMPLETED
        assert result.states["b"].status == NodeStatus.COMPLETED
        assert result.states["c"].status == NodeStatus.COMPLETED
        assert result.states["a"].result == 1
        assert result.duration > 0


# ---------------------------------------------------------------------------
# Engine — parallel DAG
# ---------------------------------------------------------------------------


class TestEngineParallel:
    @pytest.mark.asyncio
    async def test_parallel_execution(self) -> None:
        g = Graph()
        g.add_node(SimpleNode(name="a", _return_value=10, _delay=0.05))
        g.add_node(SimpleNode(name="b", _return_value=20, _delay=0.05))
        g.add_node(SimpleNode(name="c", _return_value=30, _delay=0.05))

        result = await Engine().execute(g)

        assert result.success
        # All three should run in parallel, so total time should be roughly one delay
        assert result.duration < 0.3


# ---------------------------------------------------------------------------
# Engine — diamond DAG
# ---------------------------------------------------------------------------


class TestEngineDiamond:
    @pytest.mark.asyncio
    async def test_diamond_data_flow(self) -> None:
        g = Graph()
        g.add_node(SimpleNode(name="source", _return_value=5))
        g.add_node(AdderNode(name="left", dependencies=["source"]))
        g.add_node(AdderNode(name="right", dependencies=["source"]))
        g.add_node(AdderNode(name="sink", dependencies=["left", "right"]))
        g.add_edge("source", "left")
        g.add_edge("source", "right")
        g.add_edge("left", "sink")
        g.add_edge("right", "sink")

        result = await Engine().execute(g)

        assert result.success
        assert result.states["source"].result == 5
        assert result.states["left"].result == 5
        assert result.states["right"].result == 5
        assert result.states["sink"].result == 10


# ---------------------------------------------------------------------------
# Engine — single node
# ---------------------------------------------------------------------------


class TestEngineSingleNode:
    @pytest.mark.asyncio
    async def test_single_node(self) -> None:
        g = Graph()
        g.add_node(SimpleNode(name="only", _return_value="hello"))

        result = await Engine().execute(g)

        assert result.success
        assert result.states["only"].result == "hello"


# ---------------------------------------------------------------------------
# Engine — empty graph
# ---------------------------------------------------------------------------


class TestEngineEmptyGraph:
    @pytest.mark.asyncio
    async def test_empty_graph(self) -> None:
        g = Graph()
        result = await Engine().execute(g)
        assert result.success
        assert result.states == {}
        assert result.duration >= 0


# ---------------------------------------------------------------------------
# Engine — node with error
# ---------------------------------------------------------------------------


class TestEngineNodeError:
    @pytest.mark.asyncio
    async def test_node_error_marks_failed(self) -> None:
        g = Graph()
        g.add_node(SimpleNode(name="bad", _side_effect=ValueError("boom")))

        result = await Engine().execute(g)

        assert not result.success
        assert result.states["bad"].status == NodeStatus.FAILED
        assert str(result.states["bad"].error) == "boom"


# ---------------------------------------------------------------------------
# Engine — failure policies
# ---------------------------------------------------------------------------


class TestFailurePolicy:
    @pytest.mark.asyncio
    async def test_fail_fast_skips_remaining_levels(self) -> None:
        g = Graph()
        g.add_node(SimpleNode(name="a", _side_effect=RuntimeError("fail")))
        g.add_node(SimpleNode(name="b", dependencies=["a"], _return_value=2))
        g.add_edge("a", "b")

        config = EngineConfig(failure_policy=FailurePolicy.FAIL_FAST)
        result = await Engine(config).execute(g)

        assert not result.success
        assert result.states["a"].status == NodeStatus.FAILED
        assert result.states["b"].status == NodeStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_continue_runs_all(self) -> None:
        g = Graph()
        g.add_node(SimpleNode(name="a", _side_effect=RuntimeError("fail")))
        g.add_node(SimpleNode(name="b", _return_value=2))

        config = EngineConfig(failure_policy=FailurePolicy.CONTINUE)
        result = await Engine(config).execute(g)

        assert not result.success
        assert result.states["a"].status == NodeStatus.FAILED
        assert result.states["b"].status == NodeStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_skip_dependents(self) -> None:
        g = Graph()
        g.add_node(SimpleNode(name="a", _side_effect=RuntimeError("fail")))
        g.add_node(SimpleNode(name="b", dependencies=["a"], _return_value=2))
        g.add_node(SimpleNode(name="c", _return_value=3))
        g.add_edge("a", "b")

        config = EngineConfig(failure_policy=FailurePolicy.SKIP_DEPENDENTS)
        result = await Engine(config).execute(g)

        assert not result.success
        assert result.states["a"].status == NodeStatus.FAILED
        assert result.states["b"].status == NodeStatus.SKIPPED
        assert result.states["c"].status == NodeStatus.COMPLETED


# ---------------------------------------------------------------------------
# Engine — timeout
# ---------------------------------------------------------------------------


class TestEngineTimeout:
    @pytest.mark.asyncio
    async def test_timeout_aborts_execution(self) -> None:
        g = Graph()
        g.add_node(SimpleNode(name="slow", _return_value=1, _delay=5.0))

        config = EngineConfig(timeout=0.1)
        result = await Engine(config).execute(g)

        assert not result.success


# ---------------------------------------------------------------------------
# Engine — inputs passthrough
# ---------------------------------------------------------------------------


class TestEngineInputs:
    @pytest.mark.asyncio
    async def test_initial_inputs_available(self) -> None:
        @dataclass
        class EchoNode:
            name: str
            dependencies: list[str] = field(default_factory=list)

            async def execute(self, inputs: dict[str, Any]) -> Any:
                return inputs.get("greeting", "none")

        g = Graph()
        g.add_node(EchoNode(name="echo"))

        result = await Engine().execute(g, inputs={"greeting": "hello"})

        assert result.success
        assert result.states["echo"].result == "hello"


# ---------------------------------------------------------------------------
# Engine — concurrency limiting
# ---------------------------------------------------------------------------


class TestEngineConcurrency:
    @pytest.mark.asyncio
    async def test_max_concurrency_respected(self) -> None:
        peak = 0
        current = 0
        lock = asyncio.Lock()

        @dataclass
        class TrackingNode:
            name: str
            dependencies: list[str] = field(default_factory=list)

            async def execute(self, inputs: dict[str, Any]) -> Any:
                nonlocal peak, current
                async with lock:
                    current += 1
                    if current > peak:
                        peak = current
                await asyncio.sleep(0.05)
                async with lock:
                    current -= 1
                return None

        g = Graph()
        for i in range(10):
            g.add_node(TrackingNode(name=f"n{i}"))

        config = EngineConfig(max_concurrency=3)
        result = await Engine(config).execute(g)

        assert result.success
        assert peak <= 3


# ---------------------------------------------------------------------------
# ExecutionResult / EngineConfig defaults
# ---------------------------------------------------------------------------


class TestDataclassDefaults:
    def test_engine_config_defaults(self) -> None:
        cfg = EngineConfig()
        assert cfg.max_concurrency == 10
        assert cfg.failure_policy == FailurePolicy.FAIL_FAST
        assert cfg.timeout is None

    def test_execution_result_defaults(self) -> None:
        r = ExecutionResult()
        assert r.states == {}
        assert r.duration == 0.0
        assert r.success is True
