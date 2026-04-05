"""Edge-case tests for pykit-dag."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest

from pykit_dag import Engine, EngineConfig, FailurePolicy, Graph, NodeStatus
from pykit_dag.graph import CycleError


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
# Complex Topologies
# ---------------------------------------------------------------------------


class TestComplexTopologies:
    @pytest.mark.asyncio
    async def test_multi_fan_out(self) -> None:
        """One source fans out to 5 independent nodes, all complete."""
        g = Graph()
        g.add_node(SimpleNode(name="source", _return_value=42))
        for i in range(5):
            g.add_node(SimpleNode(name=f"sink_{i}", dependencies=["source"], _return_value=i))
            g.add_edge("source", f"sink_{i}")

        result = await Engine().execute(g)

        assert result.success
        assert result.states["source"].status == NodeStatus.COMPLETED
        for i in range(5):
            assert result.states[f"sink_{i}"].status == NodeStatus.COMPLETED
            assert result.states[f"sink_{i}"].result == i

    @pytest.mark.asyncio
    async def test_multi_fan_in(self) -> None:
        """5 independent sources all feed into one sink (AdderNode)."""
        g = Graph()
        deps = []
        for i in range(5):
            name = f"src_{i}"
            deps.append(name)
            g.add_node(SimpleNode(name=name, _return_value=i + 1))

        g.add_node(AdderNode(name="sink", dependencies=deps))
        for name in deps:
            g.add_edge(name, "sink")

        result = await Engine().execute(g)

        assert result.success
        assert result.states["sink"].status == NodeStatus.COMPLETED
        assert result.states["sink"].result == 15  # 1+2+3+4+5

    @pytest.mark.asyncio
    async def test_double_diamond(self) -> None:
        """Two diamonds chained: a→(b,c)→d→(e,f)→g."""
        g = Graph()
        g.add_node(SimpleNode(name="a", _return_value=1))
        g.add_node(AdderNode(name="b", dependencies=["a"]))
        g.add_node(AdderNode(name="c", dependencies=["a"]))
        g.add_node(AdderNode(name="d", dependencies=["b", "c"]))
        g.add_node(AdderNode(name="e", dependencies=["d"]))
        g.add_node(AdderNode(name="f", dependencies=["d"]))
        g.add_node(AdderNode(name="g", dependencies=["e", "f"]))

        for src, dst in [("a","b"),("a","c"),("b","d"),("c","d"),("d","e"),("d","f"),("e","g"),("f","g")]:
            g.add_edge(src, dst)

        result = await Engine().execute(g)

        assert result.success
        assert result.states["a"].result == 1
        assert result.states["b"].result == 1
        assert result.states["c"].result == 1
        assert result.states["d"].result == 2  # b + c
        assert result.states["e"].result == 2
        assert result.states["f"].result == 2
        assert result.states["g"].result == 4  # e + f

    @pytest.mark.asyncio
    async def test_wide_layer_20_nodes(self) -> None:
        """20 independent nodes at same level, verify all complete concurrently."""
        g = Graph()
        for i in range(20):
            g.add_node(SimpleNode(name=f"n{i}", _return_value=i, _delay=0.05))

        config = EngineConfig(max_concurrency=20)
        result = await Engine(config).execute(g)

        assert result.success
        for i in range(20):
            assert result.states[f"n{i}"].status == NodeStatus.COMPLETED
            assert result.states[f"n{i}"].result == i
        # All running concurrently → much less than 20 * 0.05s = 1.0s
        assert result.duration < 0.5

    @pytest.mark.asyncio
    async def test_deep_chain_15_levels(self) -> None:
        """15 sequential nodes, each depends on previous, verify ordering preserved."""
        g = Graph()
        g.add_node(SimpleNode(name="n0", _return_value=1))
        for i in range(1, 15):
            g.add_node(AdderNode(name=f"n{i}", dependencies=[f"n{i - 1}"]))
            g.add_edge(f"n{i - 1}", f"n{i}")

        result = await Engine().execute(g)

        assert result.success
        # Each AdderNode sums its dependency: n0=1, n1=1(from n0), ...all produce 1
        for i in range(15):
            assert result.states[f"n{i}"].status == NodeStatus.COMPLETED
            assert result.states[f"n{i}"].result == 1


# ---------------------------------------------------------------------------
# Error Propagation
# ---------------------------------------------------------------------------


class TestErrorPropagation:
    @pytest.mark.asyncio
    async def test_fail_fast_with_independent_nodes(self) -> None:
        """Two independent nodes at the same level: one fails, the other still
        runs because they are gathered concurrently within the same level."""
        g = Graph()
        g.add_node(SimpleNode(name="good", _return_value=1, _delay=0.01))
        g.add_node(SimpleNode(name="bad", _side_effect=RuntimeError("boom"), _delay=0.01))

        config = EngineConfig(failure_policy=FailurePolicy.FAIL_FAST)
        result = await Engine(config).execute(g)

        assert not result.success
        assert result.states["bad"].status == NodeStatus.FAILED
        # Same-level nodes run concurrently; the good node should complete
        assert result.states["good"].status == NodeStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_skip_dependents_multi_level(self) -> None:
        """3-level chain, level 1 fails, verify level 2 and 3 all skipped."""
        g = Graph()
        g.add_node(SimpleNode(name="root", _side_effect=RuntimeError("fail")))
        g.add_node(SimpleNode(name="mid", dependencies=["root"], _return_value=2))
        g.add_node(SimpleNode(name="leaf", dependencies=["mid"], _return_value=3))
        g.add_edge("root", "mid")
        g.add_edge("mid", "leaf")

        config = EngineConfig(failure_policy=FailurePolicy.SKIP_DEPENDENTS)
        result = await Engine(config).execute(g)

        assert not result.success
        assert result.states["root"].status == NodeStatus.FAILED
        assert result.states["mid"].status == NodeStatus.SKIPPED
        assert result.states["leaf"].status == NodeStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_continue_runs_despite_failed_dependency(self) -> None:
        """CONTINUE policy: even dependent nodes attempt execution."""
        g = Graph()
        g.add_node(SimpleNode(name="fails", _side_effect=RuntimeError("boom")))
        g.add_node(SimpleNode(name="dep", dependencies=["fails"], _return_value=42))
        g.add_edge("fails", "dep")

        config = EngineConfig(failure_policy=FailurePolicy.CONTINUE)
        result = await Engine(config).execute(g)

        assert not result.success
        assert result.states["fails"].status == NodeStatus.FAILED
        # With CONTINUE the dependent node still runs
        assert result.states["dep"].status == NodeStatus.COMPLETED
        assert result.states["dep"].result == 42

    @pytest.mark.asyncio
    async def test_multiple_failures_fail_fast(self) -> None:
        """Multiple nodes at same level fail, verify fail_fast stops at next level."""
        g = Graph()
        g.add_node(SimpleNode(name="fail1", _side_effect=RuntimeError("e1")))
        g.add_node(SimpleNode(name="fail2", _side_effect=RuntimeError("e2")))
        g.add_node(SimpleNode(name="ok", _return_value=1))
        # Next level depends on level-0 nodes
        g.add_node(SimpleNode(name="next1", dependencies=["fail1"], _return_value=2))
        g.add_node(SimpleNode(name="next2", dependencies=["ok"], _return_value=3))
        g.add_edge("fail1", "next1")
        g.add_edge("ok", "next2")

        config = EngineConfig(failure_policy=FailurePolicy.FAIL_FAST)
        result = await Engine(config).execute(g)

        assert not result.success
        assert result.states["fail1"].status == NodeStatus.FAILED
        assert result.states["fail2"].status == NodeStatus.FAILED
        # Next level entirely skipped
        assert result.states["next1"].status == NodeStatus.SKIPPED
        assert result.states["next2"].status == NodeStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_error_preserves_message(self) -> None:
        """Verify the specific exception message is preserved in NodeState.error."""
        g = Graph()
        g.add_node(SimpleNode(name="err", _side_effect=ValueError("specific error 42")))

        result = await Engine().execute(g)

        assert not result.success
        assert result.states["err"].status == NodeStatus.FAILED
        assert isinstance(result.states["err"].error, ValueError)
        assert str(result.states["err"].error) == "specific error 42"


# ---------------------------------------------------------------------------
# Cycle Detection Edge Cases
# ---------------------------------------------------------------------------


class TestCycleDetection:
    def test_self_cycle(self) -> None:
        """Node depends on itself via add_edge('a', 'a'), CycleError raised."""
        g = Graph()
        g.add_node(SimpleNode(name="a"))
        g.add_edge("a", "a")

        with pytest.raises(CycleError):
            g.validate()

    def test_long_cycle_detection(self) -> None:
        """10 nodes in a ring: n0→n1→…→n9→n0."""
        g = Graph()
        for i in range(10):
            g.add_node(SimpleNode(name=f"n{i}"))
        for i in range(10):
            g.add_edge(f"n{i}", f"n{(i + 1) % 10}")

        with pytest.raises(CycleError):
            g.topological_sort()

    def test_cycle_with_branch(self) -> None:
        """Valid branch plus a cycle: a→b→c→b (c cycles back to b)."""
        g = Graph()
        g.add_node(SimpleNode(name="a"))
        g.add_node(SimpleNode(name="b"))
        g.add_node(SimpleNode(name="c"))
        g.add_node(SimpleNode(name="d"))
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_edge("c", "b")  # cycle
        g.add_edge("a", "d")  # valid branch

        with pytest.raises(CycleError):
            g.topological_sort()


# ---------------------------------------------------------------------------
# Timeout Handling
# ---------------------------------------------------------------------------


class TestTimeoutHandling:
    @pytest.mark.asyncio
    async def test_timeout_with_fast_nodes(self) -> None:
        """Timeout=1.0s with nodes completing in 10ms, verify success."""
        g = Graph()
        for i in range(5):
            g.add_node(SimpleNode(name=f"n{i}", _return_value=i, _delay=0.01))

        config = EngineConfig(timeout=1.0)
        result = await Engine(config).execute(g)

        assert result.success
        for i in range(5):
            assert result.states[f"n{i}"].status == NodeStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_timeout_partial_completion(self) -> None:
        """3 nodes: 2 fast + 1 slow(5s), timeout=0.2s, verify fast nodes completed."""
        g = Graph()
        g.add_node(SimpleNode(name="fast1", _return_value=1, _delay=0.01))
        g.add_node(SimpleNode(name="fast2", _return_value=2, _delay=0.01))
        g.add_node(SimpleNode(name="slow", _return_value=3, _delay=5.0))

        config = EngineConfig(timeout=0.2)
        result = await Engine(config).execute(g)

        assert not result.success
        assert result.states["fast1"].status == NodeStatus.COMPLETED
        assert result.states["fast2"].status == NodeStatus.COMPLETED
        # Slow node was mid-execution when timeout fired
        assert result.states["slow"].status != NodeStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_zero_timeout(self) -> None:
        """Timeout=0.001, virtually instant timeout (should fail quickly)."""
        g = Graph()
        g.add_node(SimpleNode(name="a", _return_value=1, _delay=0.1))

        config = EngineConfig(timeout=0.001)
        result = await Engine(config).execute(g)

        assert not result.success
        assert result.duration < 1.0


# ---------------------------------------------------------------------------
# Large Graphs
# ---------------------------------------------------------------------------


class TestLargeGraphs:
    @pytest.mark.asyncio
    async def test_100_node_wide_graph(self) -> None:
        """100 independent nodes, verify all complete, success=True."""
        g = Graph()
        for i in range(100):
            g.add_node(SimpleNode(name=f"n{i}", _return_value=i))

        config = EngineConfig(max_concurrency=100)
        result = await Engine(config).execute(g)

        assert result.success
        assert len(result.states) == 100
        for i in range(100):
            assert result.states[f"n{i}"].status == NodeStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_100_node_linear_chain(self) -> None:
        """100 sequential nodes in chain, verify all complete in order."""
        g = Graph()
        g.add_node(SimpleNode(name="n0", _return_value=0))
        for i in range(1, 100):
            g.add_node(SimpleNode(name=f"n{i}", dependencies=[f"n{i - 1}"], _return_value=i))
            g.add_edge(f"n{i - 1}", f"n{i}")

        result = await Engine().execute(g)

        assert result.success
        assert len(result.states) == 100
        for i in range(100):
            assert result.states[f"n{i}"].status == NodeStatus.COMPLETED
            assert result.states[f"n{i}"].result == i

    @pytest.mark.asyncio
    async def test_50_node_diamond(self) -> None:
        """1 root → 48 middle → 1 sink, verify data flows correctly."""
        g = Graph()
        g.add_node(SimpleNode(name="root", _return_value=1))

        middle_names = []
        for i in range(48):
            name = f"m{i}"
            middle_names.append(name)
            g.add_node(AdderNode(name=name, dependencies=["root"]))
            g.add_edge("root", name)

        g.add_node(AdderNode(name="sink", dependencies=middle_names))
        for name in middle_names:
            g.add_edge(name, "sink")

        config = EngineConfig(max_concurrency=50)
        result = await Engine(config).execute(g)

        assert result.success
        assert result.states["root"].result == 1
        for name in middle_names:
            assert result.states[name].result == 1
        # Sink sums all 48 middle nodes: 48 × 1 = 48
        assert result.states["sink"].result == 48


# ---------------------------------------------------------------------------
# Concurrent Execution
# ---------------------------------------------------------------------------


class TestConcurrentExecution:
    @pytest.mark.asyncio
    async def test_concurrency_limit_1_is_sequential(self) -> None:
        """max_concurrency=1, verify peak concurrent never exceeds 1."""
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
                await asyncio.sleep(0.02)
                async with lock:
                    current -= 1
                return None

        g = Graph()
        for i in range(5):
            g.add_node(TrackingNode(name=f"n{i}"))

        config = EngineConfig(max_concurrency=1)
        result = await Engine(config).execute(g)

        assert result.success
        assert peak == 1

    @pytest.mark.asyncio
    async def test_concurrency_with_dependencies(self) -> None:
        """Mix of parallel and sequential nodes, verify correct execution."""
        g = Graph()
        # Level 0: a, b (parallel)
        g.add_node(SimpleNode(name="a", _return_value=10))
        g.add_node(SimpleNode(name="b", _return_value=20))
        # Level 1: c depends on a, d depends on b (parallel)
        g.add_node(AdderNode(name="c", dependencies=["a"]))
        g.add_node(AdderNode(name="d", dependencies=["b"]))
        g.add_edge("a", "c")
        g.add_edge("b", "d")
        # Level 2: e depends on c and d
        g.add_node(AdderNode(name="e", dependencies=["c", "d"]))
        g.add_edge("c", "e")
        g.add_edge("d", "e")

        result = await Engine().execute(g)

        assert result.success
        assert result.states["a"].result == 10
        assert result.states["b"].result == 20
        assert result.states["c"].result == 10
        assert result.states["d"].result == 20
        assert result.states["e"].result == 30  # 10 + 20

    @pytest.mark.asyncio
    async def test_parallel_error_isolation(self) -> None:
        """In SKIP_DEPENDENTS: two independent chains, one fails, other succeeds."""
        g = Graph()
        # Chain 1: fails at root
        g.add_node(SimpleNode(name="c1_root", _side_effect=RuntimeError("chain1 fail")))
        g.add_node(SimpleNode(name="c1_mid", dependencies=["c1_root"], _return_value=1))
        g.add_node(SimpleNode(name="c1_leaf", dependencies=["c1_mid"], _return_value=2))
        g.add_edge("c1_root", "c1_mid")
        g.add_edge("c1_mid", "c1_leaf")

        # Chain 2: succeeds entirely
        g.add_node(SimpleNode(name="c2_root", _return_value=10))
        g.add_node(SimpleNode(name="c2_mid", dependencies=["c2_root"], _return_value=20))
        g.add_node(SimpleNode(name="c2_leaf", dependencies=["c2_mid"], _return_value=30))
        g.add_edge("c2_root", "c2_mid")
        g.add_edge("c2_mid", "c2_leaf")

        config = EngineConfig(failure_policy=FailurePolicy.SKIP_DEPENDENTS)
        result = await Engine(config).execute(g)

        assert not result.success
        # Chain 1: root failed, dependents skipped
        assert result.states["c1_root"].status == NodeStatus.FAILED
        assert result.states["c1_mid"].status == NodeStatus.SKIPPED
        assert result.states["c1_leaf"].status == NodeStatus.SKIPPED
        # Chain 2: completely unaffected
        assert result.states["c2_root"].status == NodeStatus.COMPLETED
        assert result.states["c2_mid"].status == NodeStatus.COMPLETED
        assert result.states["c2_leaf"].status == NodeStatus.COMPLETED
