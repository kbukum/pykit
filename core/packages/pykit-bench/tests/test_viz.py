"""Tests for viz/ modules — SVG chart rendering.

These modules use no external dependencies (pure SVG string building),
so no matplotlib mocking needed.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pykit_bench.curves import (
    CalibrationCurve,
    ConfusionMatrixDetail,
    RocCurve,
    ScoreDistribution,
)
from pykit_bench.result import (
    BenchRunResult,
    BenchSampleResult,
    BranchResult,
    DatasetInfo,
    MetricResult,
)
from pykit_bench.viz.calibration import render_calibration
from pykit_bench.viz.comparison import render_comparison
from pykit_bench.viz.confusion import render_confusion
from pykit_bench.viz.distribution import render_distribution
from pykit_bench.viz.render import (
    RenderOptions,
    _build_distributions,
    _decode_as,
    _extract_calibration,
    _extract_confusion_matrix,
    _extract_distributions,
    _extract_roc,
    render_all,
)
from pykit_bench.viz.roc import render_roc
from pykit_bench.viz.svg_builder import (
    Point,
    SvgBuilder,
    clamp01,
    color_at,
    draw_axes,
    heat_color,
    xml_escape,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(**overrides) -> BenchRunResult:
    defaults = dict(
        id="run-viz",
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        tag="test",
        duration_ms=100,
        dataset=DatasetInfo(name="ds", sample_count=2),
        metrics=[],
        branches={},
        samples=[],
        curves={},
    )
    defaults.update(overrides)
    return BenchRunResult(**defaults)


# ===========================================================================
# svg_builder.py
# ===========================================================================


class TestSvgBuilder:
    def test_empty_render(self):
        s = SvgBuilder(100, 50)
        svg = s.render()
        assert "<svg" in svg
        assert "</svg>" in svg
        assert 'width="100"' in svg
        assert 'height="50"' in svg

    def test_rect(self):
        s = SvgBuilder(100, 100)
        s.rect(10, 20, 30, 40, "red")
        svg = s.render()
        assert "<rect" in svg
        assert 'fill="red"' in svg

    def test_rect_f(self):
        s = SvgBuilder(100, 100)
        s.rect_f(1.5, 2.5, 3.5, 4.5, "blue", 'opacity="0.5"')
        svg = s.render()
        assert 'fill="blue"' in svg
        assert 'opacity="0.5"' in svg

    def test_line(self):
        s = SvgBuilder(100, 100)
        s.line(0, 0, 100, 100, "#333", 1.5)
        svg = s.render()
        assert "<line" in svg

    def test_text(self):
        s = SvgBuilder(100, 100)
        s.text(50, 50, "Hello <world>", "#000", 12)
        svg = s.render()
        assert "Hello &lt;world&gt;" in svg

    def test_circle(self):
        s = SvgBuilder(100, 100)
        s.circle(50, 50, 10, "green")
        svg = s.render()
        assert "<circle" in svg

    def test_polyline(self):
        s = SvgBuilder(100, 100)
        pts = [Point(0, 0), Point(50, 50), Point(100, 0)]
        s.polyline(pts, "red", 2, "none")
        svg = s.render()
        assert "<polyline" in svg

    def test_polyline_empty(self):
        s = SvgBuilder(100, 100)
        s.polyline([], "red", 2, "none")
        svg = s.render()
        assert "<polyline" not in svg


class TestSvgHelpers:
    def test_color_at_wraps(self):
        c0 = color_at(0)
        assert c0.startswith("#")
        c8 = color_at(8)
        assert c8 == c0  # wraps around palette

    def test_heat_color_extremes(self):
        light = heat_color(0.0)
        dark = heat_color(1.0)
        assert light != dark
        assert light.startswith("#")

    def test_heat_color_clamped(self):
        assert heat_color(-1.0) == heat_color(0.0)
        assert heat_color(2.0) == heat_color(1.0)

    def test_clamp01(self):
        assert clamp01(0.5) == 0.5
        assert clamp01(-1.0) == 0.0
        assert clamp01(2.0) == 1.0

    def test_xml_escape(self):
        assert xml_escape("<b>") == "&lt;b&gt;"
        assert xml_escape('"hi"') == "&quot;hi&quot;"

    def test_draw_axes(self):
        s = SvgBuilder(200, 200)
        draw_axes(s, 60, 40, 100.0, 100.0)
        svg = s.render()
        assert "<line" in svg


# ===========================================================================
# roc.py
# ===========================================================================


class TestRenderRoc:
    def test_basic_roc(self):
        roc = RocCurve(fpr=[0, 0.2, 0.5, 1.0], tpr=[0, 0.6, 0.8, 1.0], auc=0.85)
        svg = render_roc(roc)
        assert "<svg" in svg
        assert "ROC Curve" in svg
        assert "AUC = 0.8500" in svg

    def test_empty_roc(self):
        roc = RocCurve(fpr=[], tpr=[], auc=0.0)
        svg = render_roc(roc)
        assert "<svg" in svg
        # No polyline for empty data
        assert "polyline" not in svg

    def test_custom_size(self):
        roc = RocCurve(fpr=[0, 1], tpr=[0, 1], auc=0.5)
        svg = render_roc(roc, width=800, height=600)
        assert 'width="800"' in svg


# ===========================================================================
# confusion.py
# ===========================================================================


class TestRenderConfusion:
    def test_basic_confusion(self):
        cm = ConfusionMatrixDetail(labels=["pos", "neg"], matrix=[[8, 2], [1, 9]])
        svg = render_confusion(cm)
        assert "<svg" in svg
        assert "Confusion Matrix" in svg
        assert "pos" in svg
        assert "neg" in svg

    def test_empty_labels(self):
        cm = ConfusionMatrixDetail(labels=[], matrix=[])
        svg = render_confusion(cm)
        assert "<svg" in svg

    def test_custom_size(self):
        cm = ConfusionMatrixDetail(labels=["a", "b"], matrix=[[5, 1], [2, 7]])
        svg = render_confusion(cm, width=800, height=600)
        assert 'width="800"' in svg


# ===========================================================================
# distribution.py
# ===========================================================================


class TestRenderDistribution:
    def test_basic_distribution(self):
        dists = [
            ScoreDistribution(label="pos", bins=[0, 0.5, 1.0], counts=[3, 7]),
            ScoreDistribution(label="neg", bins=[0, 0.5, 1.0], counts=[6, 2]),
        ]
        svg = render_distribution(dists)
        assert "<svg" in svg
        assert "Score Distribution" in svg

    def test_empty_distributions(self):
        svg = render_distribution([])
        assert "<svg" in svg

    def test_zero_counts(self):
        dists = [ScoreDistribution(label="x", bins=[0, 0.5, 1.0], counts=[0, 0])]
        svg = render_distribution(dists)
        assert "<svg" in svg


# ===========================================================================
# comparison.py
# ===========================================================================


class TestRenderComparison:
    def test_basic_comparison(self):
        branches = {
            "b1": BranchResult(name="b1", metrics={"accuracy": 0.9, "f1": 0.85}),
            "b2": BranchResult(name="b2", metrics={"accuracy": 0.8, "f1": 0.75}),
        }
        svg = render_comparison(branches)
        assert "<svg" in svg
        assert "Branch Comparison" in svg

    def test_empty_branches(self):
        svg = render_comparison({})
        assert "<svg" in svg

    def test_no_metrics(self):
        branches = {"b1": BranchResult(name="b1", metrics={})}
        svg = render_comparison(branches)
        assert "<svg" in svg


# ===========================================================================
# calibration.py
# ===========================================================================


class TestRenderCalibration:
    def test_basic_calibration(self):
        cal = CalibrationCurve(
            predicted_probability=[0.1, 0.3, 0.5, 0.7, 0.9],
            actual_frequency=[0.08, 0.25, 0.48, 0.72, 0.91],
        )
        svg = render_calibration(cal)
        assert "<svg" in svg
        assert "Calibration Curve" in svg

    def test_empty_calibration(self):
        cal = CalibrationCurve(predicted_probability=[], actual_frequency=[])
        svg = render_calibration(cal)
        assert "<svg" in svg
        assert "polyline" not in svg


# ===========================================================================
# render.py — render_all and extraction helpers
# ===========================================================================


class TestRenderAll:
    def test_empty_result(self):
        result = _make_result()
        charts = render_all(result)
        assert isinstance(charts, dict)
        # No data → empty or minimal
        assert len(charts) == 0

    def test_with_confusion_matrix(self):
        result = _make_result(curves={"confusion_matrix": {"labels": ["a", "b"], "matrix": [[5, 1], [2, 7]]}})
        charts = render_all(result)
        assert "confusion_matrix.svg" in charts

    def test_with_roc(self):
        result = _make_result(curves={"roc": {"fpr": [0, 0.5, 1], "tpr": [0, 0.8, 1], "auc": 0.85}})
        charts = render_all(result)
        assert "roc_curve.svg" in charts

    def test_with_calibration(self):
        result = _make_result(
            curves={
                "calibration": {
                    "predicted_probability": [0.2, 0.8],
                    "actual_frequency": [0.1, 0.9],
                }
            }
        )
        charts = render_all(result)
        assert "calibration_curve.svg" in charts

    def test_with_branches(self):
        result = _make_result(branches={"b1": BranchResult(name="b1", metrics={"acc": 0.9})})
        charts = render_all(result)
        assert "branch_comparison.svg" in charts

    def test_with_samples_builds_distribution(self):
        samples = [
            BenchSampleResult(id="s1", label="pos", score=0.9, correct=True),
            BenchSampleResult(id="s2", label="neg", score=0.2, correct=True),
        ]
        result = _make_result(samples=samples)
        charts = render_all(result)
        assert "score_distribution.svg" in charts

    def test_custom_render_options(self):
        result = _make_result(curves={"roc": {"fpr": [0, 1], "tpr": [0, 1], "auc": 0.5}})
        opts = RenderOptions(width=300, height=200)
        charts = render_all(result, opts=opts)
        assert "roc_curve.svg" in charts
        assert 'width="300"' in charts["roc_curve.svg"]

    def test_with_score_distribution_curves(self):
        sd = [{"label": "pos", "bins": [0.0, 0.5, 1.0], "counts": [2, 3]}]
        result = _make_result(curves={"score_distribution": sd})
        charts = render_all(result)
        assert "score_distribution.svg" in charts


class TestDecodeAs:
    def test_direct_instance(self):
        roc = RocCurve(fpr=[0, 1], tpr=[0, 1], auc=0.5)
        assert _decode_as(roc, RocCurve) is roc

    def test_from_dict(self):
        d = {"fpr": [0, 1], "tpr": [0, 1], "auc": 0.5}
        result = _decode_as(d, RocCurve)
        assert isinstance(result, RocCurve)
        assert result.auc == 0.5

    def test_none_returns_none(self):
        assert _decode_as(None, RocCurve) is None

    def test_invalid_data(self):
        assert _decode_as(42, RocCurve) is None


class TestExtractHelpers:
    def test_extract_confusion_from_metric(self):
        metric = MetricResult(
            name="cm",
            value=0.0,
            detail={"labels": ["a", "b"], "matrix": [[5, 1], [2, 7]]},
        )
        result = _make_result(metrics=[metric])
        cm = _extract_confusion_matrix(result)
        assert cm is not None
        assert cm.labels == ["a", "b"]

    def test_extract_confusion_from_curves(self):
        result = _make_result(curves={"confusion_matrix": {"labels": ["x", "y"], "matrix": [[3, 1], [0, 6]]}})
        cm = _extract_confusion_matrix(result)
        assert cm is not None

    def test_extract_roc(self):
        result = _make_result(curves={"roc": {"fpr": [0, 1], "tpr": [0, 1], "auc": 0.5}})
        roc = _extract_roc(result)
        assert roc is not None
        assert roc.auc == 0.5

    def test_extract_roc_from_metric(self):
        metric = MetricResult(
            name="roc",
            value=0.5,
            detail={"fpr": [0, 0.5, 1], "tpr": [0, 0.8, 1], "auc": 0.8},
        )
        result = _make_result(metrics=[metric])
        roc = _extract_roc(result)
        assert roc is not None

    def test_extract_calibration(self):
        result = _make_result(
            curves={
                "calibration": {
                    "predicted_probability": [0.2, 0.8],
                    "actual_frequency": [0.15, 0.85],
                }
            }
        )
        cal = _extract_calibration(result)
        assert cal is not None

    def test_extract_calibration_from_metric(self):
        metric = MetricResult(
            name="cal",
            value=0.0,
            detail={
                "predicted_probability": [0.1, 0.9],
                "actual_frequency": [0.05, 0.95],
            },
        )
        result = _make_result(metrics=[metric])
        cal = _extract_calibration(result)
        assert cal is not None

    def test_extract_distributions_from_samples(self):
        samples = [
            BenchSampleResult(id="s1", label="pos", score=0.9, correct=True),
            BenchSampleResult(id="s2", label="neg", score=0.1, correct=True),
        ]
        result = _make_result(samples=samples)
        dists = _extract_distributions(result)
        assert len(dists) == 2
        labels = {d.label for d in dists}
        assert "pos" in labels
        assert "neg" in labels


class TestBuildDistributions:
    def test_basic(self):
        samples = [
            BenchSampleResult(id="s1", label="pos", score=0.9, correct=True),
            BenchSampleResult(id="s2", label="pos", score=0.85, correct=True),
            BenchSampleResult(id="s3", label="neg", score=0.1, correct=True),
        ]
        dists = _build_distributions(samples)
        assert len(dists) == 2

    def test_empty(self):
        dists = _build_distributions([])
        assert dists == []
