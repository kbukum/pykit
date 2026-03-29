"""Vega-Lite specification generation for benchmark visualizations."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import io

    from pykit_bench.result import BenchRunResult


class VegaLiteReporter:
    """Generates Vega-Lite specifications as JSON for embedding in dashboards."""

    @property
    def name(self) -> str:
        return "vegalite"

    def generate(self, writer: io.StringIO, result: BenchRunResult) -> None:
        """Write all Vega-Lite specs as a JSON object to *writer*."""
        specs = vegalite_specs(result)
        writer.write(json.dumps(specs, indent=2, ensure_ascii=False))


def vegalite_specs(result: BenchRunResult) -> dict[str, Any]:
    """Return a dict of chart-name → Vega-Lite spec for *result*."""
    specs: dict[str, Any] = {}

    roc = _roc_spec(result)
    if roc:
        specs["roc_curve"] = roc

    cm = _confusion_matrix_spec(result)
    if cm:
        specs["confusion_matrix"] = cm

    ts = _threshold_sweep_spec(result)
    if ts:
        specs["threshold_sweep"] = ts

    cal = _calibration_spec(result)
    if cal:
        specs["calibration"] = cal

    br = _branch_comparison_spec(result)
    if br:
        specs["branch_comparison"] = br

    sd = _score_distribution_spec(result)
    if sd:
        specs["score_distribution"] = sd

    return specs


# ------------------------------------------------------------------
# Individual spec builders
# ------------------------------------------------------------------


def _roc_spec(r: BenchRunResult) -> dict[str, Any] | None:
    """ROC curve spec from curves data."""
    roc = r.curves.get("roc")
    if not roc or not isinstance(roc, dict):
        return None
    fpr = roc.get("fpr", [])
    tpr = roc.get("tpr", [])
    if not fpr or not tpr:
        return None
    data = [{"fpr": f, "tpr": t} for f, t in zip(fpr, tpr, strict=False)]
    auc = roc.get("auc", 0.0)
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": f"ROC Curve (AUC={auc:.4f})",
        "width": 400,
        "height": 400,
        "layer": [
            {
                "data": {"values": data},
                "mark": {"type": "line", "strokeWidth": 2},
                "encoding": {
                    "x": {"field": "fpr", "type": "quantitative", "title": "False Positive Rate"},
                    "y": {"field": "tpr", "type": "quantitative", "title": "True Positive Rate"},
                },
            },
            {
                "data": {"values": [{"fpr": 0, "tpr": 0}, {"fpr": 1, "tpr": 1}]},
                "mark": {"type": "line", "strokeDash": [4, 4], "color": "gray"},
                "encoding": {
                    "x": {"field": "fpr", "type": "quantitative"},
                    "y": {"field": "tpr", "type": "quantitative"},
                },
            },
        ],
    }


def _confusion_matrix_spec(r: BenchRunResult) -> dict[str, Any] | None:
    """Heatmap spec for confusion matrix."""
    cm = r.curves.get("confusion_matrix")
    if not cm or not isinstance(cm, dict):
        # Also check metric details
        for m in r.metrics:
            if m.detail and isinstance(m.detail, dict) and "matrix" in m.detail:
                cm = m.detail
                break
    if not cm:
        return None
    labels: list[str] = cm.get("labels", [])
    matrix: list[list[int]] = cm.get("matrix", [])
    if not labels or not matrix:
        return None

    data = []
    for i, actual in enumerate(labels):
        for j, predicted in enumerate(labels):
            val = matrix[i][j] if i < len(matrix) and j < len(matrix[i]) else 0
            data.append({"actual": actual, "predicted": predicted, "count": val})

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Confusion Matrix",
        "width": 300,
        "height": 300,
        "data": {"values": data},
        "mark": "rect",
        "encoding": {
            "x": {"field": "predicted", "type": "nominal", "title": "Predicted"},
            "y": {"field": "actual", "type": "nominal", "title": "Actual"},
            "color": {"field": "count", "type": "quantitative", "scale": {"scheme": "blues"}},
            "tooltip": [
                {"field": "actual", "type": "nominal"},
                {"field": "predicted", "type": "nominal"},
                {"field": "count", "type": "quantitative"},
            ],
        },
    }


def _threshold_sweep_spec(r: BenchRunResult) -> dict[str, Any] | None:
    """Line chart for threshold sweep (precision, recall, f1 vs threshold)."""
    ts = r.curves.get("threshold_sweep")
    if not ts or not isinstance(ts, (list, dict)):
        return None

    points: list[dict[str, Any]] = []
    items = ts if isinstance(ts, list) else ts.get("points", [])
    for pt in items:
        if isinstance(pt, dict):
            thr = pt.get("threshold", 0)
            for metric in ("precision", "recall", "f1", "accuracy"):
                val = pt.get(metric)
                if val is not None:
                    points.append({"threshold": thr, "metric": metric, "value": val})

    if not points:
        return None

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Threshold Sweep",
        "width": 500,
        "height": 300,
        "data": {"values": points},
        "mark": "line",
        "encoding": {
            "x": {"field": "threshold", "type": "quantitative", "title": "Threshold"},
            "y": {"field": "value", "type": "quantitative", "title": "Value"},
            "color": {"field": "metric", "type": "nominal"},
        },
    }


def _calibration_spec(r: BenchRunResult) -> dict[str, Any] | None:
    """Calibration curve: predicted probability vs actual frequency."""
    cal = r.curves.get("calibration")
    if not cal or not isinstance(cal, dict):
        return None
    predicted = cal.get("predicted_probability", [])
    actual = cal.get("actual_frequency", [])
    if not predicted or not actual:
        return None

    data = [{"predicted": p, "actual": a} for p, a in zip(predicted, actual, strict=False)]
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Calibration Curve",
        "width": 400,
        "height": 400,
        "layer": [
            {
                "data": {"values": data},
                "mark": {"type": "point", "filled": True},
                "encoding": {
                    "x": {
                        "field": "predicted",
                        "type": "quantitative",
                        "title": "Predicted Probability",
                    },
                    "y": {
                        "field": "actual",
                        "type": "quantitative",
                        "title": "Actual Frequency",
                    },
                },
            },
            {
                "data": {"values": [{"x": 0, "y": 0}, {"x": 1, "y": 1}]},
                "mark": {"type": "line", "strokeDash": [4, 4], "color": "gray"},
                "encoding": {
                    "x": {"field": "x", "type": "quantitative"},
                    "y": {"field": "y", "type": "quantitative"},
                },
            },
        ],
    }


def _branch_comparison_spec(r: BenchRunResult) -> dict[str, Any] | None:
    """Grouped bar chart comparing branch metrics."""
    if not r.branches:
        return None

    data = []
    for bname, br in r.branches.items():
        for mname, mval in br.metrics.items():
            data.append({"branch": bname, "metric": mname, "value": mval})

    if not data:
        return None

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Branch Comparison",
        "width": 400,
        "height": 300,
        "data": {"values": data},
        "mark": "bar",
        "encoding": {
            "x": {"field": "branch", "type": "nominal", "title": "Branch"},
            "y": {"field": "value", "type": "quantitative", "title": "Value"},
            "color": {"field": "metric", "type": "nominal"},
            "xOffset": {"field": "metric"},
        },
    }


def _score_distribution_spec(r: BenchRunResult) -> dict[str, Any] | None:
    """Histogram of prediction scores grouped by correctness."""
    if not r.samples:
        return None

    # Check curves first for pre-computed distributions
    sd = r.curves.get("score_distribution")
    if sd and isinstance(sd, (list, dict)):
        items = sd if isinstance(sd, list) else [sd]
        data = []
        for dist in items:
            if isinstance(dist, dict):
                label = dist.get("label", "")
                bins = dist.get("bins", [])
                counts = dist.get("counts", [])
                for b, c in zip(bins, counts, strict=False):
                    data.append({"bin": b, "count": c, "label": label})
        if data:
            return {
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "title": "Score Distribution",
                "width": 400,
                "height": 300,
                "data": {"values": data},
                "mark": "bar",
                "encoding": {
                    "x": {"field": "bin", "type": "quantitative", "title": "Score", "bin": True},
                    "y": {"field": "count", "type": "quantitative", "title": "Count"},
                    "color": {"field": "label", "type": "nominal"},
                },
            }

    # Fall back to building from samples
    data = [
        {"score": s.score, "correct": "correct" if s.correct else "incorrect"} for s in r.samples
    ]
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Score Distribution",
        "width": 400,
        "height": 300,
        "data": {"values": data},
        "mark": "bar",
        "encoding": {
            "x": {"field": "score", "type": "quantitative", "bin": True, "title": "Score"},
            "y": {"aggregate": "count", "type": "quantitative", "title": "Count"},
            "color": {"field": "correct", "type": "nominal"},
        },
    }
