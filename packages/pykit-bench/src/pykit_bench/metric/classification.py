"""Classification metrics: binary, multi-class, confusion matrix, threshold sweep.

Mirrors gokit's ``bench/metric/classification.go``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from pykit_bench.curves import ConfusionMatrixDetail, ThresholdPoint
from pykit_bench.result import MetricResult

if TYPE_CHECKING:
    from pykit_bench.types import ScoredSample

L = TypeVar("L")

_DEFAULT_THRESHOLDS = [round(t * 0.1, 1) for t in range(1, 10)]


def _safe_divide(a: float, b: float) -> float:
    """Return 0 when denominator is 0, preventing NaN/Inf."""
    if b == 0:
        return 0.0
    return a / b


# ---------------------------------------------------------------------------
# Binary Classification
# ---------------------------------------------------------------------------


def binary_classification[L](
    positive_label: L,
    *,
    threshold: float = 0.5,
) -> _BinaryClassification[L]:
    """Create a binary classification metric.

    Args:
        positive_label: The label considered positive.
        threshold: Score threshold for positive prediction (default 0.5).
    """
    return _BinaryClassification(positive_label, threshold)


class _BinaryClassification[L]:
    """Binary classification metric computing precision, recall, F1, accuracy."""

    def __init__(self, positive_label: L, threshold: float) -> None:
        self._positive = positive_label
        self._threshold = threshold

    @property
    def name(self) -> str:
        return "binary_classification"

    def compute(self, scored: list[ScoredSample[L]]) -> MetricResult:
        if not scored:
            return MetricResult(name=self.name, value=0.0)

        tp = fp = tn = fn = 0
        for s in scored:
            actual = s.sample.label == self._positive
            predicted = s.prediction.score >= self._threshold
            if actual and predicted:
                tp += 1
            elif actual and not predicted:
                fn += 1
            elif not actual and predicted:
                fp += 1
            else:
                tn += 1

        precision = _safe_divide(float(tp), float(tp + fp))
        recall = _safe_divide(float(tp), float(tp + fn))
        f1 = _safe_divide(2.0 * precision * recall, precision + recall)
        accuracy = _safe_divide(float(tp + tn), float(len(scored)))
        fpr = _safe_divide(float(fp), float(fp + tn))

        pos_label = str(self._positive)
        neg_label = f"not_{pos_label}"

        return MetricResult(
            name=self.name,
            value=f1,
            values={
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "accuracy": accuracy,
                "fpr": fpr,
                "tp": float(tp),
                "fp": float(fp),
                "tn": float(tn),
                "fn": float(fn),
                "threshold": self._threshold,
            },
            detail=ConfusionMatrixDetail(
                labels=[pos_label, neg_label],
                matrix=[[tp, fn], [fp, tn]],
                orientation="row=actual, col=predicted",
            ),
        )


# ---------------------------------------------------------------------------
# Confusion Matrix (multi-class)
# ---------------------------------------------------------------------------


def confusion_matrix[L](labels: list[L]) -> _ConfusionMatrix[L]:
    """Create an NxN confusion matrix metric.

    Args:
        labels: Ordered list of class labels.
    """
    return _ConfusionMatrix(labels)


class _ConfusionMatrix[L]:
    """Multi-class confusion matrix."""

    def __init__(self, labels: list[L]) -> None:
        self._labels = list(labels)

    @property
    def name(self) -> str:
        return "confusion_matrix"

    def compute(self, scored: list[ScoredSample[L]]) -> MetricResult:
        n = len(self._labels)
        label_idx: dict[L, int] = {lbl: i for i, lbl in enumerate(self._labels)}
        matrix = [[0] * n for _ in range(n)]

        for s in scored:
            actual_idx = label_idx.get(s.sample.label)
            pred_idx = label_idx.get(s.prediction.label)
            if actual_idx is not None and pred_idx is not None:
                matrix[actual_idx][pred_idx] += 1

        return MetricResult(
            name=self.name,
            value=0.0,
            detail=ConfusionMatrixDetail(
                labels=[str(lbl) for lbl in self._labels],
                matrix=matrix,
                orientation="row=actual, col=predicted",
            ),
        )


# ---------------------------------------------------------------------------
# Threshold Sweep
# ---------------------------------------------------------------------------


def threshold_sweep[L](
    positive_label: L,
    thresholds: list[float] | None = None,
) -> _ThresholdSweep[L]:
    """Create a threshold sweep metric.

    Args:
        positive_label: The label considered positive.
        thresholds: Threshold values to sweep. Defaults to 0.1-0.9 in 0.1 steps.
    """
    return _ThresholdSweep(positive_label, thresholds or _DEFAULT_THRESHOLDS)


class _ThresholdSweep[L]:
    """Computes classification metrics at multiple thresholds."""

    def __init__(self, positive_label: L, thresholds: list[float]) -> None:
        self._positive = positive_label
        self._thresholds = thresholds

    @property
    def name(self) -> str:
        return "threshold_sweep"

    def compute(self, scored: list[ScoredSample[L]]) -> MetricResult:
        if not scored:
            return MetricResult(name=self.name, value=0.0)

        best_f1 = 0.0
        points: list[ThresholdPoint] = []

        for t in self._thresholds:
            tp = fp = tn = fn = 0
            for s in scored:
                actual = s.sample.label == self._positive
                predicted = s.prediction.score >= t
                if actual and predicted:
                    tp += 1
                elif actual and not predicted:
                    fn += 1
                elif not actual and predicted:
                    fp += 1
                else:
                    tn += 1

            precision = _safe_divide(float(tp), float(tp + fp))
            recall = _safe_divide(float(tp), float(tp + fn))
            f1 = _safe_divide(2.0 * precision * recall, precision + recall)
            accuracy = _safe_divide(float(tp + tn), float(len(scored)))

            if f1 > best_f1:
                best_f1 = f1

            points.append(
                ThresholdPoint(
                    threshold=t,
                    precision=precision,
                    recall=recall,
                    f1=f1,
                    accuracy=accuracy,
                )
            )

        return MetricResult(
            name=self.name,
            value=best_f1,
            detail=[p.__dict__ for p in points],
        )


# ---------------------------------------------------------------------------
# Multi-Class Classification
# ---------------------------------------------------------------------------


def multi_class_classification[L](labels: list[L]) -> _MultiClassClassification[L]:
    """Create a multi-class classification metric with macro/micro averaging.

    Args:
        labels: Ordered list of class labels.
    """
    return _MultiClassClassification(labels)


class _MultiClassClassification[L]:
    """Multi-class classification with macro and micro averaging."""

    def __init__(self, labels: list[L]) -> None:
        self._labels = list(labels)

    @property
    def name(self) -> str:
        return "multi_class_classification"

    def compute(self, scored: list[ScoredSample[L]]) -> MetricResult:
        if not scored:
            return MetricResult(name=self.name, value=0.0)

        # Per-class TP/FP/FN
        tp: dict[L, int] = {lbl: 0 for lbl in self._labels}
        fp: dict[L, int] = {lbl: 0 for lbl in self._labels}
        fn: dict[L, int] = {lbl: 0 for lbl in self._labels}

        correct = 0
        for s in scored:
            actual = s.sample.label
            predicted = s.prediction.label
            if actual == predicted:
                correct += 1
                if actual in tp:
                    tp[actual] += 1
            else:
                if actual in fn:
                    fn[actual] += 1
                if predicted in fp:
                    fp[predicted] += 1

        class_count = len(self._labels)

        # Macro average: mean of per-class metrics
        macro_precision = 0.0
        macro_recall = 0.0
        macro_f1 = 0.0
        for lbl in self._labels:
            p = _safe_divide(float(tp[lbl]), float(tp[lbl] + fp[lbl]))
            r = _safe_divide(float(tp[lbl]), float(tp[lbl] + fn[lbl]))
            f = _safe_divide(2.0 * p * r, p + r)
            macro_precision += p
            macro_recall += r
            macro_f1 += f
        macro_precision = _safe_divide(macro_precision, float(class_count))
        macro_recall = _safe_divide(macro_recall, float(class_count))
        macro_f1 = _safe_divide(macro_f1, float(class_count))

        # Micro average: aggregate TP/FP/FN
        total_tp = sum(tp.values())
        total_fp = sum(fp.values())
        total_fn = sum(fn.values())
        micro_precision = _safe_divide(float(total_tp), float(total_tp + total_fp))
        micro_recall = _safe_divide(float(total_tp), float(total_tp + total_fn))
        micro_f1 = _safe_divide(
            2.0 * micro_precision * micro_recall,
            micro_precision + micro_recall,
        )

        accuracy = _safe_divide(float(correct), float(len(scored)))

        return MetricResult(
            name=self.name,
            value=macro_f1,
            values={
                "macro_precision": macro_precision,
                "macro_recall": macro_recall,
                "macro_f1": macro_f1,
                "micro_precision": micro_precision,
                "micro_recall": micro_recall,
                "micro_f1": micro_f1,
                "accuracy": accuracy,
            },
        )
