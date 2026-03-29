"""pykit_bench.metric — Pluggable evaluation metrics."""

from __future__ import annotations

from pykit_bench.metric.adapter import RunMetric, as_run_metric, as_run_metrics
from pykit_bench.metric.base import Metric, MetricSuite
from pykit_bench.metric.classification import (
    binary_classification,
    confusion_matrix,
    multi_class_classification,
    threshold_sweep,
)
from pykit_bench.metric.composite import weighted
from pykit_bench.metric.matching import exact_match, fuzzy_match
from pykit_bench.metric.probability import auc_roc, brier_score, calibration, log_loss
from pykit_bench.metric.ranking import mean_average_precision, ndcg, precision_at_k, recall_at_k
from pykit_bench.metric.regression import mae, mse, r_squared, rmse

__all__ = [
    "Metric",
    "MetricSuite",
    "RunMetric",
    "as_run_metric",
    "as_run_metrics",
    "auc_roc",
    "binary_classification",
    "brier_score",
    "calibration",
    "confusion_matrix",
    "exact_match",
    "fuzzy_match",
    "log_loss",
    "mae",
    "mean_average_precision",
    "mse",
    "multi_class_classification",
    "ndcg",
    "precision_at_k",
    "r_squared",
    "recall_at_k",
    "rmse",
    "threshold_sweep",
    "weighted",
]
