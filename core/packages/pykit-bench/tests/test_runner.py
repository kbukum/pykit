"""Tests for bench_runner.py — BenchRunner (the new runner)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from pykit_bench.result import BenchRunResult, MetricResult
from pykit_bench.runner import BenchRunner, BranchConfig, RunOptions
from pykit_bench.types import BenchSample, Prediction

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_loader(samples: list[BenchSample[str]]) -> MagicMock:
    loader = MagicMock()
    loader.all.return_value = samples
    return loader


def _make_evaluator(
    name: str,
    label: str = "pos",
    score: float = 0.9,
    *,
    raise_exc: bool = False,
    timeout: bool = False,
) -> MagicMock:
    import asyncio

    async def _evaluate(input_data: bytes) -> Prediction[str]:
        if raise_exc:
            raise RuntimeError("boom")
        if timeout:
            await asyncio.sleep(999)
        return Prediction(label=label, score=score)

    ev = MagicMock()
    ev.name = name
    ev.evaluate = AsyncMock(side_effect=_evaluate)
    return ev


def _samples() -> list[BenchSample[str]]:
    return [
        BenchSample(id="s1", label="pos", input=b"a"),
        BenchSample(id="s2", label="neg", input=b"b"),
    ]


# ---------------------------------------------------------------------------
# RunOptions
# ---------------------------------------------------------------------------


class TestRunOptions:
    def test_defaults(self):
        opts = RunOptions()
        assert opts.concurrency == 4
        assert opts.timeout_secs == 30.0
        assert opts.tag == "default"
        assert opts.fail_on_regression is False
        assert opts.targets == {}

    def test_custom_values(self):
        opts = RunOptions(concurrency=8, timeout_secs=10.0, tag="my-tag", fail_on_regression=True)
        assert opts.concurrency == 8
        assert opts.tag == "my-tag"


# ---------------------------------------------------------------------------
# BranchConfig
# ---------------------------------------------------------------------------


class TestBranchConfig:
    def test_defaults(self):
        ev = _make_evaluator("test-ev")
        bc = BranchConfig(name="branch-a", evaluator=ev)
        assert bc.name == "branch-a"
        assert bc.tier == 0

    def test_custom_tier(self):
        ev = _make_evaluator("test-ev")
        bc = BranchConfig(name="branch-b", evaluator=ev, tier=3)
        assert bc.tier == 3


# ---------------------------------------------------------------------------
# BenchRunner builder API
# ---------------------------------------------------------------------------


class TestBenchRunnerBuilder:
    def test_register_returns_self(self):
        runner = BenchRunner()
        result = runner.register("b1", _make_evaluator("b1"))
        assert result is runner

    def test_with_metrics_returns_self(self):
        runner = BenchRunner()
        suite = MagicMock()
        result = runner.with_metrics(suite)
        assert result is runner

    def test_with_storage_returns_self(self):
        runner = BenchRunner()
        storage = MagicMock()
        result = runner.with_storage(storage)
        assert result is runner

    def test_with_reporter_returns_self(self):
        runner = BenchRunner()
        reporter = MagicMock()
        result = runner.with_reporter(reporter)
        assert result is runner

    def test_with_comparator_returns_self(self):
        runner = BenchRunner()
        comparator = MagicMock()
        result = runner.with_comparator(comparator)
        assert result is runner


# ---------------------------------------------------------------------------
# BenchRunner.run
# ---------------------------------------------------------------------------


class TestBenchRunnerRun:
    async def test_basic_run(self):
        samples = _samples()
        loader = _make_loader(samples)
        ev = _make_evaluator("branch-a", label="pos", score=0.95)

        runner = BenchRunner()
        runner.register("branch-a", ev)
        result = await runner.run(loader)

        assert isinstance(result, BenchRunResult)
        assert "branch-a" in result.branches
        assert result.dataset.sample_count == 2
        assert len(result.samples) == 2

    async def test_run_with_default_opts(self):
        loader = _make_loader(_samples())
        ev = _make_evaluator("b", label="pos", score=0.8)

        runner = BenchRunner()
        runner.register("b", ev)
        result = await runner.run(loader, opts=None)

        assert result.tag == "default"

    async def test_run_custom_tag(self):
        loader = _make_loader(_samples())
        ev = _make_evaluator("b", label="pos", score=0.8)

        runner = BenchRunner()
        runner.register("b", ev)
        opts = RunOptions(tag="custom")
        result = await runner.run(loader, opts=opts)

        assert result.tag == "custom"

    async def test_run_with_error_evaluator(self):
        loader = _make_loader(_samples())
        ev = _make_evaluator("err-branch", raise_exc=True)

        runner = BenchRunner()
        runner.register("err-branch", ev)
        result = await runner.run(loader)

        branch = result.branches["err-branch"]
        assert branch.errors == 2
        for sr in result.samples:
            assert sr.error == "evaluation failed"

    async def test_run_with_timeout(self):
        loader = _make_loader(_samples())
        ev = _make_evaluator("slow", timeout=True)

        runner = BenchRunner()
        runner.register("slow", ev)
        opts = RunOptions(timeout_secs=0.01)
        result = await runner.run(loader, opts=opts)

        branch = result.branches["slow"]
        assert branch.errors == 2

    async def test_run_with_metrics_suite(self):
        loader = _make_loader(_samples())
        ev = _make_evaluator("b", label="pos", score=0.9)

        suite = MagicMock()
        suite.compute.return_value = [MetricResult(name="test-metric", value=0.88)]

        runner = BenchRunner()
        runner.register("b", ev)
        runner.with_metrics(suite)
        result = await runner.run(loader)

        assert len(result.metrics) == 1
        assert result.metrics[0].name == "test-metric"

    async def test_run_with_storage(self):
        loader = _make_loader(_samples())
        ev = _make_evaluator("b", label="pos", score=0.9)
        storage = MagicMock()

        runner = BenchRunner()
        runner.register("b", ev)
        runner.with_storage(storage)
        await runner.run(loader)

        storage.save.assert_called_once()

    async def test_run_with_reporter(self):
        loader = _make_loader(_samples())
        ev = _make_evaluator("b", label="pos", score=0.9)
        reporter = MagicMock()

        runner = BenchRunner()
        runner.register("b", ev)
        runner.with_reporter(reporter)
        await runner.run(loader)

        reporter.generate.assert_called_once()

    async def test_run_reporter_exception_is_swallowed(self):
        loader = _make_loader(_samples())
        ev = _make_evaluator("b", label="pos", score=0.9)
        reporter = MagicMock()
        reporter.generate.side_effect = RuntimeError("report failed")

        runner = BenchRunner()
        runner.register("b", ev)
        runner.with_reporter(reporter)
        result = await runner.run(loader)
        assert isinstance(result, BenchRunResult)

    async def test_run_with_comparator_no_regression(self):
        loader = _make_loader(_samples())
        ev = _make_evaluator("b", label="pos", score=0.9)

        storage = MagicMock()
        prev_result = MagicMock()
        prev_result.id = "old-run"
        storage.latest.return_value = prev_result

        diff = MagicMock()
        diff.has_regression.return_value = False
        comparator = MagicMock()
        comparator.compare.return_value = diff

        runner = BenchRunner()
        runner.register("b", ev)
        runner.with_storage(storage)
        runner.with_comparator(comparator)
        result = await runner.run(loader)

        comparator.compare.assert_called_once()
        assert isinstance(result, BenchRunResult)

    async def test_run_with_comparator_regression_raises(self):
        loader = _make_loader(_samples())
        ev = _make_evaluator("b", label="pos", score=0.9)

        storage = MagicMock()
        prev_result = MagicMock()
        prev_result.id = "old-run"
        storage.latest.return_value = prev_result

        diff = MagicMock()
        diff.has_regression.return_value = True
        diff.summary.return_value = "accuracy dropped"
        comparator = MagicMock()
        comparator.compare.return_value = diff

        runner = BenchRunner()
        runner.register("b", ev)
        runner.with_storage(storage)
        runner.with_comparator(comparator)
        opts = RunOptions(fail_on_regression=True)

        with pytest.raises(RuntimeError, match="Regression detected"):
            await runner.run(loader, opts=opts)

    async def test_run_comparator_no_previous_run(self):
        """Comparator gracefully handles FileNotFoundError from storage.latest()."""
        loader = _make_loader(_samples())
        ev = _make_evaluator("b", label="pos", score=0.9)

        storage = MagicMock()
        storage.latest.side_effect = FileNotFoundError("No runs")

        comparator = MagicMock()

        runner = BenchRunner()
        runner.register("b", ev)
        runner.with_storage(storage)
        runner.with_comparator(comparator)
        result = await runner.run(loader)

        comparator.compare.assert_not_called()
        assert isinstance(result, BenchRunResult)

    async def test_multiple_branches(self):
        samples = _samples()
        loader = _make_loader(samples)
        ev1 = _make_evaluator("b1", label="pos", score=0.9)
        ev2 = _make_evaluator("b2", label="neg", score=0.3)

        runner = BenchRunner()
        runner.register("b1", ev1)
        runner.register("b2", ev2)
        result = await runner.run(loader)

        assert "b1" in result.branches
        assert "b2" in result.branches

    async def test_branch_accuracy_computed(self):
        samples = [
            BenchSample(id="s1", label="pos", input=b"a"),
            BenchSample(id="s2", label="pos", input=b"b"),
        ]
        loader = _make_loader(samples)
        ev = _make_evaluator("b", label="pos", score=0.95)

        runner = BenchRunner()
        runner.register("b", ev)
        result = await runner.run(loader)

        assert result.branches["b"].metrics["accuracy"] == 1.0
