"""Curve data types for visualization.

These types are populated by metrics and stored in run results
for visualization by report and viz sub-modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RocCurve:
    """Receiver Operating Characteristic curve data."""

    fpr: list[float] = field(default_factory=list)
    """False Positive Rates."""

    tpr: list[float] = field(default_factory=list)
    """True Positive Rates."""

    thresholds: list[float] = field(default_factory=list)
    """Classification thresholds."""

    auc: float = 0.0
    """Area Under Curve."""


@dataclass
class PrecisionRecallCurve:
    """Precision-Recall curve data."""

    precision: list[float] = field(default_factory=list)
    recall: list[float] = field(default_factory=list)
    thresholds: list[float] = field(default_factory=list)


@dataclass
class CalibrationCurve:
    """Calibration curve: predicted probability vs actual frequency."""

    predicted_probability: list[float] = field(default_factory=list)
    actual_frequency: list[float] = field(default_factory=list)
    bin_count: list[int] = field(default_factory=list)


@dataclass
class ConfusionMatrixDetail:
    """Full NxN confusion matrix with labels."""

    labels: list[str] = field(default_factory=list)
    """Class labels."""

    matrix: list[list[int]] = field(default_factory=list)
    """NxN matrix (row=actual, col=predicted)."""

    orientation: str = "row=actual, col=predicted"
    """Orientation description."""


@dataclass
class ScoreDistribution:
    """Score distribution for a single label."""

    label: str = ""
    """Label for this distribution."""

    bins: list[float] = field(default_factory=list)
    """Histogram bin edges."""

    counts: list[int] = field(default_factory=list)
    """Counts per bin."""


@dataclass
class ThresholdPoint:
    """Classification metrics at a specific threshold."""

    threshold: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    accuracy: float = 0.0
