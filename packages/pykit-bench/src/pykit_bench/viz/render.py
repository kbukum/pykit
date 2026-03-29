"""High-level render_all orchestrator and options."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pykit_bench.curves import (
    CalibrationCurve,
    ConfusionMatrixDetail,
    RocCurve,
    ScoreDistribution,
)
from pykit_bench.viz.calibration import render_calibration
from pykit_bench.viz.comparison import render_comparison
from pykit_bench.viz.confusion import render_confusion
from pykit_bench.viz.distribution import render_distribution
from pykit_bench.viz.roc import render_roc

if TYPE_CHECKING:
    from pykit_bench.result import BenchRunResult, BenchSampleResult


@dataclass
class RenderOptions:
    """Configuration for SVG rendering."""

    width: int = 600
    height: int = 400


def render_all(result: BenchRunResult, opts: RenderOptions | None = None) -> dict[str, str]:
    """Generate all available SVG charts from a benchmark run result.

    Returns a mapping of ``filename → SVG content``.  Only charts whose
    prerequisite data exists in *result* are included.
    """
    cfg = opts or RenderOptions()
    out: dict[str, str] = {}

    # Confusion matrix
    cm = _extract_confusion_matrix(result)
    if cm is not None:
        out["confusion_matrix.svg"] = render_confusion(cm, cfg.width, cfg.height)

    # ROC curve
    roc = _extract_roc(result)
    if roc is not None:
        out["roc_curve.svg"] = render_roc(roc, cfg.width, cfg.height)

    # Calibration curve
    cal = _extract_calibration(result)
    if cal is not None:
        out["calibration_curve.svg"] = render_calibration(cal, cfg.width, cfg.height)

    # Score distribution
    dists = _extract_distributions(result)
    if dists:
        out["score_distribution.svg"] = render_distribution(dists, cfg.width, cfg.height)

    # Branch comparison
    if result.branches:
        out["branch_comparison.svg"] = render_comparison(result.branches, cfg.width, cfg.height)

    return out


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


def _decode_as[T](v: Any, cls: type[T]) -> T | None:
    """Attempt to coerce *v* into *cls*.

    Handles direct instances, dicts (via JSON round-trip for dataclasses),
    and already-decoded Pydantic models.
    """
    if v is None:
        return None
    if isinstance(v, cls):
        return v
    # Dict / list - try JSON round-trip into a dataclass
    try:
        raw = json.dumps(v) if not isinstance(v, str) else v
        data = json.loads(raw)
        if isinstance(data, dict):
            return cls(**data)
    except (TypeError, json.JSONDecodeError, KeyError):
        pass
    return None


def _extract_confusion_matrix(r: BenchRunResult) -> ConfusionMatrixDetail | None:
    # Check metric details first
    for m in r.metrics:
        cm = _decode_as(m.detail, ConfusionMatrixDetail)
        if cm is not None and cm.labels:
            return cm
    # Also check curves map
    raw = r.curves.get("confusion_matrix")
    if raw is not None:
        return _decode_as(raw, ConfusionMatrixDetail)
    return None


def _extract_roc(r: BenchRunResult) -> RocCurve | None:
    raw = r.curves.get("roc")
    if raw is not None:
        roc = _decode_as(raw, RocCurve)
        if roc is not None and roc.fpr:
            return roc
    for m in r.metrics:
        roc = _decode_as(m.detail, RocCurve)
        if roc is not None and roc.fpr:
            return roc
    return None


def _extract_calibration(r: BenchRunResult) -> CalibrationCurve | None:
    raw = r.curves.get("calibration")
    if raw is not None:
        cal = _decode_as(raw, CalibrationCurve)
        if cal is not None and cal.predicted_probability:
            return cal
    for m in r.metrics:
        cal = _decode_as(m.detail, CalibrationCurve)
        if cal is not None and cal.predicted_probability:
            return cal
    return None


def _extract_distributions(r: BenchRunResult) -> list[ScoreDistribution]:
    # From curves map
    raw = r.curves.get("score_distribution")
    if raw is not None:
        try:
            items = json.loads(json.dumps(raw)) if not isinstance(raw, list) else raw
            if isinstance(items, list):
                dists = [_decode_as(item, ScoreDistribution) for item in items]
                valid = [d for d in dists if d is not None]
                if valid:
                    return valid
        except (TypeError, json.JSONDecodeError):
            pass
    # Build from samples
    if r.samples:
        return _build_distributions(r.samples)
    return []


def _build_distributions(
    samples: list[BenchSampleResult],
) -> list[ScoreDistribution]:
    """Create 10-bin score distributions grouped by label."""
    num_bins = 10

    by_label: dict[str, list[float]] = {}
    for s in samples:
        by_label.setdefault(s.label, []).append(s.score)

    dists: list[ScoreDistribution] = []
    for label in sorted(by_label):
        scores = by_label[label]
        bins = [i / num_bins for i in range(num_bins + 1)]
        counts = [0] * num_bins
        for sc in scores:
            idx = int(sc * num_bins)
            idx = max(0, min(num_bins - 1, idx))
            counts[idx] += 1
        dists.append(ScoreDistribution(label=label, bins=bins, counts=counts))
    return dists
