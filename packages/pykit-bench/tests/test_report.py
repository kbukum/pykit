"""Tests for report.py — MarkdownReporter and JsonReporter (old-style runner reports)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from pykit_bench.metrics import ConfusionMatrix, ThresholdMetrics
from pykit_bench.report import JsonReporter, MarkdownReporter
from pykit_bench.runner import RunResult, SampleResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run_result(
    *,
    per_branch: dict | None = None,
    misclassified: bool = False,
) -> RunResult:
    cm = ConfusionMatrix(tp=8, fp=1, tn=9, fn=2)
    metrics = ThresholdMetrics(
        threshold=0.5,
        precision=0.889,
        recall=0.8,
        f1=0.842,
        accuracy=0.85,
        fpr=0.1,
        confusion=cm,
    )

    sample_results = [
        SampleResult(
            sample_id="s1",
            label="positive",
            is_positive=True,
            overall_score=0.9,
            branch_scores={"branch-a": 0.9},
        ),
        SampleResult(
            sample_id="s2",
            label="negative",
            is_positive=False,
            overall_score=0.2,
            branch_scores={"branch-a": 0.2},
        ),
    ]

    if misclassified:
        # A positive sample scored below threshold → misclassified
        sample_results.append(
            SampleResult(
                sample_id="s3",
                label="positive",
                is_positive=True,
                overall_score=0.3,
                branch_scores={"branch-a": 0.3},
            )
        )
        # A negative sample scored above threshold → misclassified
        sample_results.append(
            SampleResult(
                sample_id="s4",
                label="negative",
                is_positive=False,
                overall_score=0.7,
                branch_scores={"branch-a": 0.7},
            )
        )

    return RunResult(
        run_id="test-run-001",
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        tag="test",
        dataset_name="test-ds",
        sample_results=sample_results,
        metrics=metrics,
        per_branch=per_branch or {},
    )


# ---------------------------------------------------------------------------
# MarkdownReporter
# ---------------------------------------------------------------------------


class TestMarkdownReporter:
    def test_generate_basic(self):
        result = _make_run_result()
        report = MarkdownReporter().generate(result)

        assert "BENCH RUN: test-run-001" in report
        assert "Precision: 0.889" in report
        assert "Recall: 0.800" in report
        assert "F1: 0.842" in report
        assert "CONFUSION MATRIX" in report
        assert "8 (TP)" in report
        assert "1 (FP)" in report

    def test_generate_with_tag(self):
        result = _make_run_result()
        report = MarkdownReporter().generate(result)
        assert "Tag: test" in report

    def test_generate_no_tag(self):
        result = _make_run_result()
        result.tag = ""
        report = MarkdownReporter().generate(result)
        assert "Tag:" not in report

    def test_generate_with_per_branch(self):
        branch_metrics = ThresholdMetrics(
            threshold=0.5,
            precision=0.9,
            recall=0.85,
            f1=0.874,
            accuracy=0.88,
            fpr=0.05,
        )
        result = _make_run_result(per_branch={"branch-a": branch_metrics})
        report = MarkdownReporter().generate(result)

        assert "PER-BRANCH BREAKDOWN" in report
        assert "branch-a" in report
        assert "WEAKEST BRANCH" in report

    def test_generate_with_misclassified(self):
        result = _make_run_result(misclassified=True)
        report = MarkdownReporter().generate(result)
        assert "MISCLASSIFIED SAMPLES" in report

    def test_generate_sample_counts(self):
        result = _make_run_result()
        report = MarkdownReporter().generate(result)
        # 2 samples: s1 is positive, s2 is negative
        assert "1 positive" in report
        assert "1 negative" in report


# ---------------------------------------------------------------------------
# JsonReporter
# ---------------------------------------------------------------------------


class TestJsonReporter:
    def test_generate_returns_dict(self):
        result = _make_run_result()
        output = JsonReporter().generate(result)
        assert isinstance(output, dict)

    def test_generate_contains_run_id(self):
        result = _make_run_result()
        output = JsonReporter().generate(result)
        assert output["run_id"] == "test-run-001"

    def test_generate_is_json_serializable(self):
        result = _make_run_result()
        output = JsonReporter().generate(result)
        # Should not raise
        json_str = json.dumps(output, default=str)
        assert isinstance(json_str, str)
