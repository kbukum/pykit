"""Regression metrics: MAE, MSE, RMSE, R².

Mirrors gokit's ``bench/metric/regression.go``.
Uses ``ScoredSample[float]`` where ``sample.label`` is actual and
``prediction.score`` is predicted.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from pykit_bench.result import MetricResult

if TYPE_CHECKING:
    from pykit_bench.types import ScoredSample


def _safe_divide(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return a / b


# ---------------------------------------------------------------------------
# MAE (Mean Absolute Error)
# ---------------------------------------------------------------------------


def mae() -> _Mae:
    """Create a Mean Absolute Error metric (lower is better)."""
    return _Mae()


class _Mae:
    """Mean Absolute Error."""

    @property
    def name(self) -> str:
        return "mae"

    def compute(self, scored: list[ScoredSample[float]]) -> MetricResult:
        if not scored:
            return MetricResult(name=self.name, value=0.0)

        total = sum(abs(s.prediction.score - s.sample.label) for s in scored)
        return MetricResult(name=self.name, value=total / len(scored))


# ---------------------------------------------------------------------------
# MSE (Mean Squared Error)
# ---------------------------------------------------------------------------


def mse() -> _Mse:
    """Create a Mean Squared Error metric (lower is better)."""
    return _Mse()


class _Mse:
    """Mean Squared Error."""

    @property
    def name(self) -> str:
        return "mse"

    def compute(self, scored: list[ScoredSample[float]]) -> MetricResult:
        if not scored:
            return MetricResult(name=self.name, value=0.0)

        total = sum((s.prediction.score - s.sample.label) ** 2 for s in scored)
        return MetricResult(name=self.name, value=total / len(scored))


# ---------------------------------------------------------------------------
# RMSE (Root Mean Squared Error)
# ---------------------------------------------------------------------------


def rmse() -> _Rmse:
    """Create a Root Mean Squared Error metric (lower is better)."""
    return _Rmse()


class _Rmse:
    """Root Mean Squared Error."""

    @property
    def name(self) -> str:
        return "rmse"

    def compute(self, scored: list[ScoredSample[float]]) -> MetricResult:
        if not scored:
            return MetricResult(name=self.name, value=0.0)

        total = sum((s.prediction.score - s.sample.label) ** 2 for s in scored)
        return MetricResult(name=self.name, value=math.sqrt(total / len(scored)))


# ---------------------------------------------------------------------------
# R² (Coefficient of Determination)
# ---------------------------------------------------------------------------


def r_squared() -> _RSquared:
    """Create an R² metric (higher is better, max 1.0)."""
    return _RSquared()


class _RSquared:
    """Coefficient of Determination (R²)."""

    @property
    def name(self) -> str:
        return "r_squared"

    def compute(self, scored: list[ScoredSample[float]]) -> MetricResult:
        if not scored:
            return MetricResult(name=self.name, value=0.0)

        mean_actual = sum(s.sample.label for s in scored) / len(scored)

        ss_res = sum((s.sample.label - s.prediction.score) ** 2 for s in scored)
        ss_tot = sum((s.sample.label - mean_actual) ** 2 for s in scored)

        r2 = 1.0 - _safe_divide(ss_res, ss_tot)

        return MetricResult(
            name=self.name,
            value=r2,
            values={
                "ss_res": ss_res,
                "ss_tot": ss_tot,
            },
        )
