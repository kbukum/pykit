"""Tests for pykit.bench.storage and pykit.bench.compare modules."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from pykit_bench.compare import RunComparator
from pykit_bench.metrics import ConfusionMatrix, ThresholdMetrics
from pykit_bench.runner import RunResult, SampleResult
from pykit_bench.storage import RunStorage


def _make_run(
    run_id: str,
    f1: float,
    samples: list[SampleResult] | None = None,
    per_branch: dict | None = None,
) -> RunResult:
    """Helper to create a minimal RunResult."""
    return RunResult(
        run_id=run_id,
        timestamp=datetime.now(tz=UTC),
        tag="test",
        dataset_name="test-ds",
        sample_results=samples or [],
        metrics=ThresholdMetrics(
            threshold=0.5,
            precision=f1,
            recall=f1,
            f1=f1,
            accuracy=f1,
            fpr=0.0,
            confusion=ConfusionMatrix(tp=1, fp=0, tn=1, fn=0),
        ),
        per_branch=per_branch or {},
    )


class TestRunStorage:
    def test_save_and_load(self, tmp_path: Path) -> None:
        storage = RunStorage(tmp_path / "results")
        run = _make_run("run-001", 0.85)
        storage.save(run)
        loaded = storage.load("run-001")
        assert loaded.run_id == "run-001"
        assert loaded.metrics.f1 == 0.85

    def test_load_nonexistent(self, tmp_path: Path) -> None:
        storage = RunStorage(tmp_path / "results")
        with pytest.raises(FileNotFoundError, match="Run not found"):
            storage.load("nonexistent")

    def test_latest(self, tmp_path: Path) -> None:
        storage = RunStorage(tmp_path / "results")
        storage.save(_make_run("run-a", 0.7))
        storage.save(_make_run("run-b", 0.9))
        latest = storage.latest()
        assert latest.run_id == "run-b"

    def test_latest_empty(self, tmp_path: Path) -> None:
        storage = RunStorage(tmp_path / "results")
        with pytest.raises(FileNotFoundError, match="No runs found"):
            storage.latest()

    def test_list_runs(self, tmp_path: Path) -> None:
        storage = RunStorage(tmp_path / "results")
        storage.save(_make_run("text-v1", 0.7))
        storage.save(_make_run("image-v1", 0.9))
        all_runs = storage.list_runs()
        assert len(all_runs) == 2

    def test_list_runs_filter(self, tmp_path: Path) -> None:
        storage = RunStorage(tmp_path / "results")
        storage.save(_make_run("text-v1", 0.7))
        storage.save(_make_run("image-v1", 0.9))
        text_runs = storage.list_runs(media_type="text")
        assert len(text_runs) == 1
        assert text_runs[0].run_id == "text-v1"

    def test_generate_run_id(self, tmp_path: Path) -> None:
        storage = RunStorage(tmp_path / "results")
        rid = storage.generate_run_id("my-dataset")
        assert rid.startswith("my-dataset-")
        assert len(rid) > len("my-dataset-")


class TestRunComparator:
    def test_improved_run(self) -> None:
        samples_a = [
            SampleResult(sample_id="s1", label="pos", is_positive=True, overall_score=0.3),
            SampleResult(sample_id="s2", label="neg", is_positive=False, overall_score=0.2),
        ]
        samples_b = [
            SampleResult(sample_id="s1", label="pos", is_positive=True, overall_score=0.8),
            SampleResult(sample_id="s2", label="neg", is_positive=False, overall_score=0.2),
        ]
        run_a = _make_run("run-a", 0.0, samples=samples_a)
        run_b = _make_run("run-b", 1.0, samples=samples_b)

        comp = RunComparator()
        result = comp.compare(run_a, run_b)

        assert result.improved
        assert result.f1_delta == 1.0
        assert "s1" in result.fixed_samples
        assert len(result.regressed_samples) == 0

    def test_regressed_run(self) -> None:
        samples_a = [
            SampleResult(sample_id="s1", label="pos", is_positive=True, overall_score=0.8),
        ]
        samples_b = [
            SampleResult(sample_id="s1", label="pos", is_positive=True, overall_score=0.3),
        ]
        run_a = _make_run("run-a", 1.0, samples=samples_a)
        run_b = _make_run("run-b", 0.0, samples=samples_b)

        result = RunComparator().compare(run_a, run_b)
        assert not result.improved
        assert "s1" in result.regressed_samples

    def test_branch_diffs(self) -> None:
        branch_a = {
            "forensic": ThresholdMetrics(
                threshold=0.5, precision=0.5, recall=0.5, f1=0.5, accuracy=0.5, fpr=0.0
            ),
        }
        branch_b = {
            "forensic": ThresholdMetrics(
                threshold=0.5, precision=1.0, recall=1.0, f1=1.0, accuracy=1.0, fpr=0.0
            ),
        }
        run_a = _make_run("a", 0.5, per_branch=branch_a)
        run_b = _make_run("b", 1.0, per_branch=branch_b)

        result = RunComparator().compare(run_a, run_b)
        assert len(result.branch_diffs) == 1
        assert result.branch_diffs[0].f1_delta == 0.5
        assert result.branch_diffs[0].improved

    def test_summary_output(self) -> None:
        run_a = _make_run("run-old", 0.6)
        run_b = _make_run("run-new", 0.9)
        result = RunComparator().compare(run_a, run_b)
        summary = result.summary()
        assert "IMPROVED" in summary
        assert "run-old" in summary
        assert "run-new" in summary
