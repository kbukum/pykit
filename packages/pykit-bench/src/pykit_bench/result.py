"""Result types for bench runs.

These types represent the complete output of a benchmark evaluation,
designed for cross-language compatibility with gokit and ruskit.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — Pydantic needs this at runtime
from typing import Any

from pydantic import BaseModel, Field

from pykit_bench import schema


class DatasetInfo(BaseModel):
    """Dataset metadata included in run results."""

    name: str
    """Dataset name from manifest."""

    version: str = ""
    """Dataset version."""

    sample_count: int = 0
    """Total samples evaluated."""

    label_distribution: dict[str, int] = Field(default_factory=dict)
    """Count of each label."""


class MetricResult(BaseModel):
    """Result of a single metric computation."""

    name: str
    """Metric name."""

    value: float = 0.0
    """Primary scalar result."""

    values: dict[str, float] = Field(default_factory=dict)
    """Per-label or secondary metrics."""

    detail: Any = None
    """Complex metric structure (confusion matrix, ROC curve, etc.)."""


class BranchResult(BaseModel):
    """Per-branch evaluation results."""

    name: str
    """Branch/evaluator name."""

    tier: int = 0
    """Tiering level."""

    metrics: dict[str, float] = Field(default_factory=dict)
    """Metrics for this branch."""

    avg_score_positive: float = 0.0
    """Average confidence on correct predictions."""

    avg_score_negative: float = 0.0
    """Average confidence on incorrect predictions."""

    duration_ms: int = 0
    """Branch evaluation time in milliseconds."""

    errors: int = 0
    """Count of errors during evaluation."""


class BenchSampleResult(BaseModel):
    """Per-sample evaluation details."""

    id: str
    """Sample ID."""

    label: str
    """Ground-truth label."""

    predicted: str = ""
    """Predicted label."""

    score: float = 0.0
    """Prediction confidence score."""

    correct: bool = False
    """Whether prediction matched ground truth."""

    branch_scores: dict[str, float] = Field(default_factory=dict)
    """Scores from all branches."""

    duration_ms: int = 0
    """Evaluation time in milliseconds."""

    error: str = ""
    """Error message if evaluation failed."""


class BenchRunResult(BaseModel):
    """Complete result of a benchmark run.

    This is the canonical output format, compatible across gokit, ruskit, and pykit.
    """

    id: str
    """Generated run identifier."""

    schema_url: str = Field(default=schema.SCHEMA_URL, alias="$schema")
    """Schema URL for validation."""

    version: str = schema.SCHEMA_VERSION
    """Schema version string."""

    timestamp: datetime
    """Run start time."""

    tag: str = ""
    """User-provided tag."""

    duration_ms: int = 0
    """Total run duration in milliseconds."""

    dataset: DatasetInfo
    """Dataset metadata."""

    metrics: list[MetricResult] = Field(default_factory=list)
    """Top-level metrics."""

    branches: dict[str, BranchResult] = Field(default_factory=dict)
    """Per-branch results."""

    samples: list[BenchSampleResult] = Field(default_factory=list)
    """Per-sample results."""

    curves: dict[str, Any] = Field(default_factory=dict)
    """Optional visualization curves."""

    model_config = {"populate_by_name": True}


class BenchRunSummary(BaseModel):
    """Lightweight run summary for listing."""

    id: str
    """Run ID."""

    timestamp: datetime
    """When run executed."""

    tag: str = ""
    """User tag."""

    dataset: str = ""
    """Dataset name."""

    f1: float = 0.0
    """F1 metric (if available)."""
