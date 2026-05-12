"""Composite metrics: weighted combination.

Mirrors gokit's ``bench/metric/composite.go``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from pykit_bench.result import MetricResult

if TYPE_CHECKING:
    from pykit_bench.metric.base import Metric
    from pykit_bench.types import ScoredSample

L = TypeVar("L")


def weighted[L](weights: dict[Metric[L], float]) -> _Weighted[L]:
    """Create a weighted composite metric.

    The result is the weighted sum of component metric values.
    Weights are not normalized — caller is responsible for their sum.

    Args:
        weights: Mapping of metric to its weight.
    """
    return _Weighted(weights)


class _Weighted[L]:
    """Weighted combination of multiple metrics."""

    def __init__(self, weights: dict[Metric[L], float]) -> None:
        self._weights = weights

    @property
    def name(self) -> str:
        parts = [f"{m.name}*{w}" for m, w in self._weights.items()]
        return f"weighted({'+'.join(parts)})"

    def compute(self, scored: list[ScoredSample[L]]) -> MetricResult:
        composite = 0.0
        values: dict[str, float] = {}
        details: list[MetricResult] = []

        for metric, weight in self._weights.items():
            result = metric.compute(scored)
            composite += result.value * weight
            values[result.name] = result.value
            details.append(result)

        return MetricResult(
            name=self.name,
            value=composite,
            values=values,
            detail=[d.model_dump() for d in details],
        )
