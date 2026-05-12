"""Matching metrics: exact match and fuzzy match.

Mirrors gokit's ``bench/metric/matching.go``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from pykit_bench.result import MetricResult

if TYPE_CHECKING:
    from pykit_bench.types import ScoredSample

L = TypeVar("L")


def _safe_divide(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return a / b


def _levenshtein_distance(a: str, b: str) -> int:
    """Compute Levenshtein edit distance via dynamic programming."""
    n, m = len(a), len(b)
    if n == 0:
        return m
    if m == 0:
        return n

    # Use single-row optimization
    prev = list(range(m + 1))
    curr = [0] * (m + 1)

    for i in range(1, n + 1):
        curr[0] = i
        for j in range(1, m + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(
                prev[j] + 1,  # deletion
                curr[j - 1] + 1,  # insertion
                prev[j - 1] + cost,  # substitution
            )
        prev, curr = curr, prev

    return prev[m]


def _levenshtein_similarity(a: str, b: str) -> float:
    """Compute similarity as 1 - (distance / max_len). Range [0, 1]."""
    max_len = max(len(a), len(b))
    if max_len == 0:
        return 1.0
    return 1.0 - _levenshtein_distance(a, b) / max_len


# ---------------------------------------------------------------------------
# Exact Match
# ---------------------------------------------------------------------------


def exact_match() -> _ExactMatch[L]:
    """Create an exact match metric (generic over any comparable label)."""
    return _ExactMatch()


class _ExactMatch[L]:
    """Fraction of predictions that exactly match the ground-truth label."""

    @property
    def name(self) -> str:
        return "exact_match"

    def compute(self, scored: list[ScoredSample[L]]) -> MetricResult:
        if not scored:
            return MetricResult(name=self.name, value=0.0)

        correct = sum(1 for s in scored if s.prediction.label == s.sample.label)
        return MetricResult(
            name=self.name,
            value=_safe_divide(float(correct), float(len(scored))),
        )


# ---------------------------------------------------------------------------
# Fuzzy Match (string labels only)
# ---------------------------------------------------------------------------


def fuzzy_match(threshold: float = 0.8) -> _FuzzyMatch:
    """Create a fuzzy match metric using Levenshtein similarity.

    Args:
        threshold: Minimum similarity to count as a match (default 0.8).
    """
    return _FuzzyMatch(threshold)


class _FuzzyMatch:
    """Fuzzy string matching via Levenshtein similarity."""

    def __init__(self, threshold: float) -> None:
        self._threshold = threshold

    @property
    def name(self) -> str:
        return "fuzzy_match"

    def compute(self, scored: list[ScoredSample[str]]) -> MetricResult:
        if not scored:
            return MetricResult(name=self.name, value=0.0)

        matches = 0
        sum_similarity = 0.0
        for s in scored:
            sim = _levenshtein_similarity(
                str(s.sample.label),
                str(s.prediction.label),
            )
            sum_similarity += sim
            if sim >= self._threshold:
                matches += 1

        return MetricResult(
            name=self.name,
            value=_safe_divide(float(matches), float(len(scored))),
            values={
                "mean_similarity": sum_similarity / len(scored),
                "threshold": self._threshold,
            },
        )
