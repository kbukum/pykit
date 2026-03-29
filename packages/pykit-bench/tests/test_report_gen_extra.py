"""Extra tests for report_gen — VegaLite and Markdown reporter gaps."""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime

from pykit_bench.report_gen.csv_reporter import CsvReporter
from pykit_bench.report_gen.json_reporter import JsonReporter as JsonReporterV2
from pykit_bench.report_gen.markdown import MarkdownReporter as MdReporterV2
from pykit_bench.report_gen.vegalite import VegaLiteReporter, vegalite_specs
from pykit_bench.result import (
    BenchRunResult,
    BenchSampleResult,
    BranchResult,
    DatasetInfo,
    MetricResult,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(**overrides) -> BenchRunResult:
    defaults = dict(
        id="run-001",
        timestamp=datetime(2025, 1, 15, 12, 0, tzinfo=UTC),
        tag="test",
        duration_ms=1234,
        dataset=DatasetInfo(name="ds", sample_count=4, label_distribution={"pos": 2, "neg": 2}),
        metrics=[
            MetricResult(name="accuracy", value=0.85, values={"precision": 0.9, "recall": 0.8}),
        ],
        branches={
            "b1": BranchResult(
                name="b1",
                tier=0,
                metrics={"accuracy": 0.85, "f1": 0.82},
                avg_score_positive=0.9,
                avg_score_negative=0.3,
                duration_ms=500,
                errors=0,
            ),
        },
        samples=[
            BenchSampleResult(id="s1", label="pos", predicted="pos", score=0.9, correct=True),
            BenchSampleResult(id="s2", label="neg", predicted="neg", score=0.2, correct=True),
            BenchSampleResult(id="s3", label="pos", predicted="neg", score=0.4, correct=False),
            BenchSampleResult(id="s4", label="neg", predicted="pos", score=0.7, correct=False),
        ],
        curves={},
    )
    defaults.update(overrides)
    return BenchRunResult(**defaults)


# ===========================================================================
# VegaLiteReporter
# ===========================================================================


class TestVegaLiteReporter:
    def test_name(self):
        assert VegaLiteReporter().name == "vegalite"

    def test_generate_writes_json(self):
        result = _make_result()
        w = io.StringIO()
        VegaLiteReporter().generate(w, result)
        output = w.getvalue()
        data = json.loads(output)
        assert isinstance(data, dict)


class TestVegaLiteSpecs:
    def test_empty_curves_still_returns_samples_chart(self):
        result = _make_result()
        specs = vegalite_specs(result)
        # score_distribution should exist from samples fallback
        assert "score_distribution" in specs
        # branch_comparison from branches
        assert "branch_comparison" in specs

    def test_roc_curve(self):
        result = _make_result(curves={"roc": {"fpr": [0, 0.5, 1], "tpr": [0, 0.8, 1], "auc": 0.9}})
        specs = vegalite_specs(result)
        assert "roc_curve" in specs
        assert "ROC Curve" in specs["roc_curve"]["title"]

    def test_roc_missing_data(self):
        result = _make_result(curves={"roc": {"fpr": [], "tpr": []}})
        specs = vegalite_specs(result)
        assert "roc_curve" not in specs

    def test_roc_non_dict(self):
        result = _make_result(curves={"roc": "not-a-dict"})
        specs = vegalite_specs(result)
        assert "roc_curve" not in specs

    def test_confusion_matrix_from_curves(self):
        cm_data = {"labels": ["pos", "neg"], "matrix": [[8, 2], [1, 9]]}
        result = _make_result(curves={"confusion_matrix": cm_data})
        specs = vegalite_specs(result)
        assert "confusion_matrix" in specs

    def test_confusion_matrix_from_metric_detail(self):
        metric = MetricResult(
            name="cm",
            value=0.0,
            detail={"labels": ["a", "b"], "matrix": [[5, 1], [2, 7]]},
        )
        result = _make_result(metrics=[metric])
        specs = vegalite_specs(result)
        assert "confusion_matrix" in specs

    def test_confusion_matrix_missing(self):
        result = _make_result(metrics=[])
        specs = vegalite_specs(result)
        assert "confusion_matrix" not in specs

    def test_threshold_sweep_from_list(self):
        points = [
            {"threshold": 0.3, "precision": 0.8, "recall": 0.9, "f1": 0.85},
            {"threshold": 0.5, "precision": 0.85, "recall": 0.8, "f1": 0.82},
        ]
        result = _make_result(curves={"threshold_sweep": points})
        specs = vegalite_specs(result)
        assert "threshold_sweep" in specs

    def test_threshold_sweep_from_dict(self):
        ts = {
            "points": [
                {"threshold": 0.3, "precision": 0.8, "recall": 0.9, "accuracy": 0.85},
            ]
        }
        result = _make_result(curves={"threshold_sweep": ts})
        specs = vegalite_specs(result)
        assert "threshold_sweep" in specs

    def test_threshold_sweep_empty(self):
        result = _make_result(curves={"threshold_sweep": []})
        specs = vegalite_specs(result)
        assert "threshold_sweep" not in specs

    def test_calibration_spec(self):
        cal = {"predicted_probability": [0.1, 0.5, 0.9], "actual_frequency": [0.05, 0.45, 0.88]}
        result = _make_result(curves={"calibration": cal})
        specs = vegalite_specs(result)
        assert "calibration" in specs

    def test_calibration_missing_data(self):
        result = _make_result(curves={"calibration": {"predicted_probability": [], "actual_frequency": []}})
        specs = vegalite_specs(result)
        assert "calibration" not in specs

    def test_branch_comparison_empty(self):
        result = _make_result(branches={})
        specs = vegalite_specs(result)
        assert "branch_comparison" not in specs

    def test_branch_comparison_no_metrics(self):
        result = _make_result(branches={"b1": BranchResult(name="b1", metrics={})})
        specs = vegalite_specs(result)
        assert "branch_comparison" not in specs

    def test_score_distribution_from_curves(self):
        sd = [{"label": "pos", "bins": [0.0, 0.5, 1.0], "counts": [2, 3]}]
        result = _make_result(curves={"score_distribution": sd})
        specs = vegalite_specs(result)
        assert "score_distribution" in specs

    def test_score_distribution_fallback_to_samples(self):
        result = _make_result()
        specs = vegalite_specs(result)
        assert "score_distribution" in specs

    def test_no_samples_no_distribution(self):
        result = _make_result(samples=[])
        specs = vegalite_specs(result)
        assert "score_distribution" not in specs


# ===========================================================================
# MarkdownReporter (report_gen/markdown.py)
# ===========================================================================


class TestMdReporterV2:
    def test_name(self):
        assert MdReporterV2().name == "markdown"

    def test_summary_section(self):
        result = _make_result()
        w = io.StringIO()
        MdReporterV2().generate(w, result)
        text = w.getvalue()
        assert "# Benchmark Report: run-001" in text
        assert "**Run ID**" in text
        assert "**Tag**" in text
        assert "**Samples**" in text

    def test_metrics_section(self):
        result = _make_result()
        w = io.StringIO()
        MdReporterV2().generate(w, result)
        text = w.getvalue()
        assert "## Metrics" in text
        assert "accuracy" in text

    def test_no_metrics(self):
        result = _make_result(metrics=[])
        w = io.StringIO()
        MdReporterV2().generate(w, result)
        text = w.getvalue()
        assert "## Metrics" not in text

    def test_confusion_matrix_section(self):
        cm_data = {"labels": ["pos", "neg"], "matrix": [[8, 2], [1, 9]]}
        result = _make_result(curves={"confusion_matrix": cm_data})
        w = io.StringIO()
        MdReporterV2().generate(w, result)
        text = w.getvalue()
        assert "## Confusion Matrix" in text

    def test_no_confusion_matrix(self):
        result = _make_result(metrics=[])
        w = io.StringIO()
        MdReporterV2().generate(w, result)
        text = w.getvalue()
        assert "## Confusion Matrix" not in text

    def test_branches_section(self):
        result = _make_result()
        w = io.StringIO()
        MdReporterV2().generate(w, result)
        text = w.getvalue()
        assert "## Branches" in text
        assert "b1" in text

    def test_no_branches(self):
        result = _make_result(branches={})
        w = io.StringIO()
        MdReporterV2().generate(w, result)
        text = w.getvalue()
        assert "## Branches" not in text

    def test_samples_section(self):
        result = _make_result()
        w = io.StringIO()
        MdReporterV2().generate(w, result)
        text = w.getvalue()
        assert "## Samples" in text
        assert "✅" in text
        assert "❌" in text

    def test_no_samples(self):
        result = _make_result(samples=[])
        w = io.StringIO()
        MdReporterV2().generate(w, result)
        text = w.getvalue()
        assert "## Samples" not in text

    def test_samples_truncation(self):
        many = [
            BenchSampleResult(id=f"s{i}", label="x", predicted="x", score=0.5, correct=True)
            for i in range(60)
        ]
        result = _make_result(samples=many)
        w = io.StringIO()
        MdReporterV2().generate(w, result)
        text = w.getvalue()
        assert "showing 50 of 60" in text

    def test_find_confusion_matrix_from_metric_detail(self):
        metric = MetricResult(
            name="cm",
            value=0.0,
            detail={"labels": ["a", "b"], "matrix": [[1, 0], [0, 1]]},
        )
        result = _make_result(metrics=[metric])
        w = io.StringIO()
        MdReporterV2().generate(w, result)
        text = w.getvalue()
        assert "## Confusion Matrix" in text


# ===========================================================================
# CsvReporter
# ===========================================================================


class TestCsvReporter:
    def test_name(self):
        assert CsvReporter().name == "csv"

    def test_generates_csv(self):
        result = _make_result()
        w = io.StringIO()
        CsvReporter().generate(w, result)
        text = w.getvalue()
        assert "metric_name,value,details" in text
        assert "accuracy" in text

    def test_sub_values_expanded(self):
        result = _make_result()
        w = io.StringIO()
        CsvReporter().generate(w, result)
        text = w.getvalue()
        assert "accuracy.precision" in text
        assert "accuracy.recall" in text


# ===========================================================================
# JsonReporter (report_gen)
# ===========================================================================


class TestJsonReporterV2:
    def test_name(self):
        assert JsonReporterV2().name == "json"

    def test_generates_valid_json(self):
        result = _make_result()
        w = io.StringIO()
        JsonReporterV2().generate(w, result)
        data = json.loads(w.getvalue())
        assert data["id"] == "run-001"
        assert "$schema" in data
