"""Accuracy metric computation for benchmarking."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConfusionMatrix:
    """Binary confusion matrix."""

    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0

    @property
    def total(self) -> int:
        return self.tp + self.fp + self.tn + self.fn


@dataclass
class ThresholdMetrics:
    """Metrics computed at a specific decision threshold."""

    threshold: float
    precision: float
    recall: float
    f1: float
    accuracy: float
    fpr: float
    confusion: ConfusionMatrix = field(default_factory=ConfusionMatrix)


def compute_metrics(
    scores: list[float],
    labels: list[bool],
    threshold: float = 0.5,
) -> ThresholdMetrics:
    """Compute precision, recall, F1, accuracy at given threshold.

    Args:
        scores: Predicted scores (0.0 to 1.0).
        labels: True = positive (e.g., AI-generated).
        threshold: Decision boundary.
    """
    if len(scores) != len(labels):
        msg = f"scores ({len(scores)}) and labels ({len(labels)}) must have same length"
        raise ValueError(msg)

    if not scores:
        return ThresholdMetrics(threshold=threshold, precision=0.0, recall=0.0, f1=0.0, accuracy=0.0, fpr=0.0)

    cm = ConfusionMatrix()
    for score, label in zip(scores, labels, strict=True):
        predicted_positive = score >= threshold
        if label and predicted_positive:
            cm.tp += 1
        elif label and not predicted_positive:
            cm.fn += 1
        elif not label and predicted_positive:
            cm.fp += 1
        else:
            cm.tn += 1

    precision = cm.tp / (cm.tp + cm.fp) if (cm.tp + cm.fp) > 0 else 0.0
    recall = cm.tp / (cm.tp + cm.fn) if (cm.tp + cm.fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (cm.tp + cm.tn) / cm.total if cm.total > 0 else 0.0
    fpr = cm.fp / (cm.fp + cm.tn) if (cm.fp + cm.tn) > 0 else 0.0

    return ThresholdMetrics(
        threshold=threshold,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        accuracy=round(accuracy, 4),
        fpr=round(fpr, 4),
        confusion=cm,
    )


def threshold_sweep(
    scores: list[float],
    labels: list[bool],
    thresholds: list[float] | None = None,
) -> list[ThresholdMetrics]:
    """Compute metrics at multiple thresholds."""
    if thresholds is None:
        thresholds = [round(t * 0.1, 1) for t in range(1, 10)]
    return [compute_metrics(scores, labels, t) for t in thresholds]


def per_branch_metrics(
    branch_scores: dict[str, list[float]],
    labels: list[bool],
    threshold: float = 0.5,
) -> dict[str, ThresholdMetrics]:
    """Compute metrics per analysis branch."""
    return {name: compute_metrics(scores, labels, threshold) for name, scores in branch_scores.items()}
