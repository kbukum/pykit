"""Base metric protocol and suite."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar

if TYPE_CHECKING:
    from pykit_bench.result import MetricResult
    from pykit_bench.types import ScoredSample

L = TypeVar("L")


class Metric(Protocol[L]):
    """A pluggable evaluation metric.

    Mirrors gokit's ``metric.Metric[L]`` interface.
    """

    @property
    def name(self) -> str:
        """Return the metric's unique name."""
        ...

    def compute(self, scored: list[ScoredSample[L]]) -> MetricResult:
        """Compute the metric over scored samples."""
        ...


class MetricSuite[L]:
    """Groups multiple metrics for batch evaluation."""

    def __init__(self, metrics: list[Metric[L]] | None = None) -> None:
        self._metrics: list[Metric[L]] = list(metrics) if metrics else []

    def add(self, metric: Metric[L]) -> None:
        self._metrics.append(metric)

    def compute(self, scored: list[ScoredSample[L]]) -> list[MetricResult]:
        return [m.compute(scored) for m in self._metrics]
