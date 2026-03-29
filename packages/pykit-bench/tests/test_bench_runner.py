"""Tests for pykit.bench.runner — BenchRunner orchestration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pykit_bench.dataset import DatasetLoader
from pykit_bench.runner import BenchRunner, RunResult


@pytest.fixture
def dataset_dir(tmp_path: Path) -> Path:
    """Create a minimal 4-sample dataset."""
    ai_dir = tmp_path / "ai"
    human_dir = tmp_path / "human"
    ai_dir.mkdir()
    human_dir.mkdir()

    (ai_dir / "a1.txt").write_text("AI text one")
    (ai_dir / "a2.txt").write_text("AI text two")
    (human_dir / "h1.txt").write_text("Human text one")
    (human_dir / "h2.txt").write_text("Human text two")

    manifest = {
        "name": "mini-test",
        "samples": [
            {"id": "ai-1", "file": "ai/a1.txt", "label": "positive"},
            {"id": "ai-2", "file": "ai/a2.txt", "label": "positive"},
            {"id": "human-1", "file": "human/h1.txt", "label": "negative"},
            {"id": "human-2", "file": "human/h2.txt", "label": "negative"},
        ],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    return tmp_path


class TestBenchRunner:
    @pytest.mark.asyncio
    async def test_perfect_branch(self, dataset_dir: Path) -> None:
        """A branch that perfectly separates classes should give F1=1.0."""

        async def perfect_branch(content: bytes, _cfg: object = None) -> float:
            return 0.9 if b"AI" in content else 0.1

        loader = DatasetLoader(dataset_dir)
        runner = BenchRunner(dataset_loader=loader, positive_label="positive")
        runner.register_branch("perfect", perfect_branch, tier=1)
        result = await runner.run(tag="test")

        assert result.metrics.f1 == 1.0
        assert result.metrics.precision == 1.0
        assert result.metrics.recall == 1.0
        assert len(result.sample_results) == 4

    @pytest.mark.asyncio
    async def test_random_branch(self, dataset_dir: Path) -> None:
        """A branch returning 0.5 for everything produces poor metrics."""

        async def constant_branch(content: bytes, _cfg: object = None) -> float:
            return 0.5

        loader = DatasetLoader(dataset_dir)
        runner = BenchRunner(dataset_loader=loader, positive_label="positive")
        runner.register_branch("constant", constant_branch, tier=1)
        result = await runner.run(tag="test")

        # 0.5 == threshold → all predicted positive → recall=1.0 but precision=0.5
        assert result.metrics.recall == 1.0
        assert result.metrics.precision == 0.5

    @pytest.mark.asyncio
    async def test_multiple_branches_decisiveness(self, dataset_dir: Path) -> None:
        """With two branches, the more decisive one dominates."""

        async def strong_branch(content: bytes, _cfg: object = None) -> float:
            return 0.95 if b"AI" in content else 0.05

        async def weak_branch(content: bytes, _cfg: object = None) -> float:
            return 0.5  # neutral — shouldn't affect outcome much

        loader = DatasetLoader(dataset_dir)
        runner = BenchRunner(dataset_loader=loader, positive_label="positive")
        runner.register_branch("strong", strong_branch, tier=1)
        runner.register_branch("weak", weak_branch, tier=1)
        result = await runner.run(tag="test")

        assert result.metrics.f1 == 1.0
        for sr in result.sample_results:
            assert "strong" in sr.branch_scores
            assert "weak" in sr.branch_scores

    @pytest.mark.asyncio
    async def test_branch_exception_handled(self, dataset_dir: Path) -> None:
        """A branch that throws gets score 0.0 instead of crashing the run."""

        async def failing_branch(content: bytes, _cfg: object = None) -> float:
            raise RuntimeError("boom")

        loader = DatasetLoader(dataset_dir)
        runner = BenchRunner(dataset_loader=loader, positive_label="positive")
        runner.register_branch("failing", failing_branch, tier=1)
        result = await runner.run(tag="test")

        assert len(result.sample_results) == 4
        for sr in result.sample_results:
            assert sr.branch_scores["failing"] == 0.0

    @pytest.mark.asyncio
    async def test_run_result_structure(self, dataset_dir: Path) -> None:
        """RunResult has all expected fields populated."""

        async def branch(content: bytes, _cfg: object = None) -> float:
            return 0.7

        loader = DatasetLoader(dataset_dir)
        runner = BenchRunner(dataset_loader=loader, positive_label="positive")
        runner.register_branch("b", branch, tier=2)
        result = await runner.run(tag="my-tag", threshold=0.6)

        assert result.tag == "my-tag"
        assert result.dataset_name == "mini-test"
        assert result.config["threshold"] == 0.6
        assert result.config["branches"] == ["b"]
        assert "b" in result.per_branch

    @pytest.mark.asyncio
    async def test_storage_integration(self, dataset_dir: Path, tmp_path: Path) -> None:
        """When storage is provided, results are persisted."""
        from pykit_bench.storage import RunStorage

        async def branch(content: bytes, _cfg: object = None) -> float:
            return 0.8

        results_dir = tmp_path / "results"
        storage = RunStorage(results_dir)
        loader = DatasetLoader(dataset_dir)
        runner = BenchRunner(
            dataset_loader=loader, positive_label="positive", storage=storage
        )
        runner.register_branch("b", branch)
        result = await runner.run(tag="persist-test")

        # Verify file was saved
        saved_files = list(results_dir.glob("*.json"))
        assert len(saved_files) == 1
        assert result.run_id in saved_files[0].stem

        # Verify round-trip
        loaded = storage.load(result.run_id)
        assert loaded.metrics.f1 == result.metrics.f1
        assert len(loaded.sample_results) == 4
