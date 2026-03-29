"""Probability metrics: AUC-ROC, Brier score, log loss, calibration.

Mirrors gokit's ``bench/metric/probability.go``.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, TypeVar

from pykit_bench.curves import CalibrationCurve, RocCurve
from pykit_bench.result import MetricResult

if TYPE_CHECKING:
    from pykit_bench.types import ScoredSample

L = TypeVar("L")


def _safe_divide(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return a / b


# ---------------------------------------------------------------------------
# AUC-ROC
# ---------------------------------------------------------------------------


def auc_roc[L](positive_label: L) -> _AucRoc[L]:
    """Create an AUC-ROC metric.

    Args:
        positive_label: The label considered positive.
    """
    return _AucRoc(positive_label)


class _AucRoc[L]:
    """Area Under the ROC Curve via trapezoidal integration."""

    def __init__(self, positive_label: L) -> None:
        self._positive = positive_label

    @property
    def name(self) -> str:
        return "auc_roc"

    def compute(self, scored: list[ScoredSample[L]]) -> MetricResult:
        if not scored:
            return MetricResult(name=self.name, value=0.0)

        total_pos = sum(1 for s in scored if s.sample.label == self._positive)
        total_neg = len(scored) - total_pos

        if total_pos == 0 or total_neg == 0:
            return MetricResult(name=self.name, value=0.0)

        # Sort by score descending
        sorted_samples = sorted(scored, key=lambda s: s.prediction.score, reverse=True)

        fpr_list: list[float] = [0.0]
        tpr_list: list[float] = [0.0]
        thresholds: list[float] = []

        tp = 0
        fp = 0
        for s in sorted_samples:
            if s.sample.label == self._positive:
                tp += 1
            else:
                fp += 1
            fpr_list.append(_safe_divide(float(fp), float(total_neg)))
            tpr_list.append(_safe_divide(float(tp), float(total_pos)))
            thresholds.append(s.prediction.score)

        # Trapezoidal integration
        auc = 0.0
        for i in range(1, len(fpr_list)):
            dx = fpr_list[i] - fpr_list[i - 1]
            auc += dx * (tpr_list[i] + tpr_list[i - 1]) / 2.0

        return MetricResult(
            name=self.name,
            value=auc,
            detail=RocCurve(
                fpr=fpr_list,
                tpr=tpr_list,
                thresholds=thresholds,
                auc=auc,
            ),
        )


# ---------------------------------------------------------------------------
# Brier Score
# ---------------------------------------------------------------------------


def brier_score[L](positive_label: L) -> _BrierScore[L]:
    """Create a Brier score metric (lower is better).

    Args:
        positive_label: The label considered positive.
    """
    return _BrierScore(positive_label)


class _BrierScore[L]:
    """Mean squared error between predicted probability and actual outcome."""

    def __init__(self, positive_label: L) -> None:
        self._positive = positive_label

    @property
    def name(self) -> str:
        return "brier_score"

    def compute(self, scored: list[ScoredSample[L]]) -> MetricResult:
        if not scored:
            return MetricResult(name=self.name, value=0.0)

        total = 0.0
        for s in scored:
            actual = 1.0 if s.sample.label == self._positive else 0.0
            diff = s.prediction.score - actual
            total += diff * diff

        return MetricResult(
            name=self.name,
            value=total / len(scored),
        )


# ---------------------------------------------------------------------------
# Log Loss (Cross-Entropy)
# ---------------------------------------------------------------------------


def log_loss[L](positive_label: L) -> _LogLoss[L]:
    """Create a log loss (cross-entropy) metric (lower is better).

    Args:
        positive_label: The label considered positive.
    """
    return _LogLoss(positive_label)


class _LogLoss[L]:
    """Binary cross-entropy loss with epsilon clamping."""

    _EPSILON = 1e-15

    def __init__(self, positive_label: L) -> None:
        self._positive = positive_label

    @property
    def name(self) -> str:
        return "log_loss"

    def compute(self, scored: list[ScoredSample[L]]) -> MetricResult:
        if not scored:
            return MetricResult(name=self.name, value=0.0)

        total = 0.0
        for s in scored:
            actual = 1.0 if s.sample.label == self._positive else 0.0
            p = max(self._EPSILON, min(1.0 - self._EPSILON, s.prediction.score))
            total += actual * math.log(p) + (1.0 - actual) * math.log(1.0 - p)

        return MetricResult(
            name=self.name,
            value=-total / len(scored),
        )


# ---------------------------------------------------------------------------
# Calibration (Expected Calibration Error)
# ---------------------------------------------------------------------------


def calibration[L](positive_label: L, *, bins: int = 10) -> _Calibration[L]:
    """Create a calibration metric (ECE, lower is better).

    Args:
        positive_label: The label considered positive.
        bins: Number of calibration bins (default 10).
    """
    return _Calibration(positive_label, bins)


class _Calibration[L]:
    """Expected Calibration Error with binned probabilities."""

    def __init__(self, positive_label: L, bins: int) -> None:
        self._positive = positive_label
        self._bins = bins

    @property
    def name(self) -> str:
        return "calibration"

    def compute(self, scored: list[ScoredSample[L]]) -> MetricResult:
        if not scored:
            return MetricResult(name=self.name, value=0.0)

        n_bins = self._bins
        bin_width = 1.0 / n_bins
        bin_count = [0] * n_bins
        bin_pos_count = [0] * n_bins
        bin_score_sum = [0.0] * n_bins

        for s in scored:
            idx = int(s.prediction.score / bin_width)
            idx = max(0, min(n_bins - 1, idx))
            bin_count[idx] += 1
            bin_score_sum[idx] += s.prediction.score
            if s.sample.label == self._positive:
                bin_pos_count[idx] += 1

        total = float(len(scored))
        predicted_prob = [0.0] * n_bins
        actual_freq = [0.0] * n_bins
        ece = 0.0

        for i in range(n_bins):
            if bin_count[i] > 0:
                predicted_prob[i] = bin_score_sum[i] / bin_count[i]
                actual_freq[i] = float(bin_pos_count[i]) / bin_count[i]
                ece += (bin_count[i] / total) * abs(actual_freq[i] - predicted_prob[i])

        return MetricResult(
            name=self.name,
            value=ece,
            detail=CalibrationCurve(
                predicted_probability=predicted_prob,
                actual_frequency=actual_freq,
                bin_count=bin_count,
            ),
        )
