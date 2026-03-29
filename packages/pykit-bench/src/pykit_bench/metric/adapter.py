"""Adapter to convert Metric to RunMetric for use with BenchRunner."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar

if TYPE_CHECKING:
    from pykit_bench.result import MetricResult
    from pykit_bench.types import ScoredSample

L = TypeVar("L")


class RunMetric(Protocol[L]):
    """Protocol matching what BenchRunner expects from a metric."""

    @property
    def name(self) -> str: ...

    def compute(self, scored: list[ScoredSample[L]]) -> MetricResult: ...


def as_run_metric(metric: object) -> RunMetric:  # type: ignore[type-arg]
    """Convert a Metric to a RunMetric.

    Since Metric and RunMetric share the same structural protocol,
    this is a no-op identity cast.
    """
    return metric  # type: ignore[return-value]


def as_run_metrics(metrics: list[object]) -> list[RunMetric]:  # type: ignore[type-arg]
    """Convert a list of Metrics to RunMetrics."""
    return [as_run_metric(m) for m in metrics]
