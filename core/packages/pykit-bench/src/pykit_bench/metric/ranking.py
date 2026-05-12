"""Ranking metrics: NDCG, MAP, Precision@K, Recall@K.

Mirrors gokit's ``bench/metric/ranking.go``.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, TypeVar

from pykit_bench.result import MetricResult

if TYPE_CHECKING:
    from pykit_bench.types import ScoredSample

L = TypeVar("L")


def _safe_divide(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return a / b


# ---------------------------------------------------------------------------
# NDCG (Normalized Discounted Cumulative Gain)
# ---------------------------------------------------------------------------


def ndcg(k: int = 0) -> _Ndcg[L]:
    """Create an NDCG metric.

    Args:
        k: Number of top results to consider. 0 means use all.
    """
    return _Ndcg(k)


class _Ndcg[L]:
    """Normalized Discounted Cumulative Gain."""

    def __init__(self, k: int) -> None:
        self._k = k

    @property
    def name(self) -> str:
        return f"ndcg@{self._k}" if self._k > 0 else "ndcg"

    def compute(self, scored: list[ScoredSample[L]]) -> MetricResult:
        if not scored:
            return MetricResult(name=self.name, value=0.0)

        sorted_samples = sorted(scored, key=lambda s: s.prediction.score, reverse=True)
        n = len(sorted_samples)
        if self._k > 0 and self._k < n:
            n = self._k

        # Relevance: 1 if predicted label matches actual label, else 0
        relevances = [
            1.0 if sorted_samples[i].prediction.label == sorted_samples[i].sample.label else 0.0
            for i in range(n)
        ]

        # DCG
        dcg = 0.0
        for i in range(n):
            dcg += relevances[i] / math.log2(i + 2)

        # Ideal DCG: sort relevances descending
        ideal_rel = sorted(relevances, reverse=True)
        ideal_dcg = 0.0
        for i in range(n):
            ideal_dcg += ideal_rel[i] / math.log2(i + 2)

        ndcg_val = _safe_divide(dcg, ideal_dcg)

        return MetricResult(
            name=self.name,
            value=ndcg_val,
            values={
                "dcg": dcg,
                "ideal_dcg": ideal_dcg,
            },
        )


# ---------------------------------------------------------------------------
# Mean Average Precision
# ---------------------------------------------------------------------------


def mean_average_precision[L](positive_label: L) -> _MeanAveragePrecision[L]:
    """Create a Mean Average Precision (MAP) metric.

    Args:
        positive_label: The label considered relevant.
    """
    return _MeanAveragePrecision(positive_label)


class _MeanAveragePrecision[L]:
    """Mean Average Precision over ranked results."""

    def __init__(self, positive_label: L) -> None:
        self._positive = positive_label

    @property
    def name(self) -> str:
        return "mean_average_precision"

    def compute(self, scored: list[ScoredSample[L]]) -> MetricResult:
        if not scored:
            return MetricResult(name=self.name, value=0.0)

        sorted_samples = sorted(scored, key=lambda s: s.prediction.score, reverse=True)
        total_relevant = sum(1 for s in scored if s.sample.label == self._positive)

        if total_relevant == 0:
            return MetricResult(name=self.name, value=0.0)

        relevant = 0
        sum_precision = 0.0
        for i, s in enumerate(sorted_samples):
            if s.sample.label == self._positive:
                relevant += 1
                sum_precision += relevant / (i + 1)

        return MetricResult(
            name=self.name,
            value=sum_precision / total_relevant,
        )


# ---------------------------------------------------------------------------
# Precision@K
# ---------------------------------------------------------------------------


def precision_at_k[L](positive_label: L, k: int) -> _PrecisionAtK[L]:
    """Create a Precision@K metric.

    Args:
        positive_label: The label considered relevant.
        k: Number of top results to evaluate.
    """
    return _PrecisionAtK(positive_label, k)


class _PrecisionAtK[L]:
    """Precision in the top-K ranked results."""

    def __init__(self, positive_label: L, k: int) -> None:
        self._positive = positive_label
        self._k = k

    @property
    def name(self) -> str:
        return f"precision@{self._k}"

    def compute(self, scored: list[ScoredSample[L]]) -> MetricResult:
        if not scored:
            return MetricResult(name=self.name, value=0.0)

        sorted_samples = sorted(scored, key=lambda s: s.prediction.score, reverse=True)
        n = min(self._k, len(sorted_samples))

        relevant = sum(1 for i in range(n) if sorted_samples[i].sample.label == self._positive)

        return MetricResult(
            name=self.name,
            value=_safe_divide(float(relevant), float(n)),
        )


# ---------------------------------------------------------------------------
# Recall@K
# ---------------------------------------------------------------------------


def recall_at_k[L](positive_label: L, k: int) -> _RecallAtK[L]:
    """Create a Recall@K metric.

    Args:
        positive_label: The label considered relevant.
        k: Number of top results to evaluate.
    """
    return _RecallAtK(positive_label, k)


class _RecallAtK[L]:
    """Recall of relevant items in the top-K ranked results."""

    def __init__(self, positive_label: L, k: int) -> None:
        self._positive = positive_label
        self._k = k

    @property
    def name(self) -> str:
        return f"recall@{self._k}"

    def compute(self, scored: list[ScoredSample[L]]) -> MetricResult:
        if not scored:
            return MetricResult(name=self.name, value=0.0)

        sorted_samples = sorted(scored, key=lambda s: s.prediction.score, reverse=True)
        n = min(self._k, len(sorted_samples))

        total_relevant = sum(1 for s in scored if s.sample.label == self._positive)
        if total_relevant == 0:
            return MetricResult(name=self.name, value=0.0)

        relevant_in_k = sum(1 for i in range(n) if sorted_samples[i].sample.label == self._positive)

        return MetricResult(
            name=self.name,
            value=_safe_divide(float(relevant_in_k), float(total_relevant)),
        )
