"""pykit_bench — Generic accuracy benchmarking framework."""

from pykit_bench.compare import ComparisonResult, RunComparator
from pykit_bench.dataset import DatasetLoader, DatasetManifest, Label, Sample
from pykit_bench.metrics import (
    ConfusionMatrix,
    ThresholdMetrics,
    compute_metrics,
    per_branch_metrics,
    threshold_sweep,
)
from pykit_bench.report import JsonReporter, MarkdownReporter
from pykit_bench.runner import BenchRunner, BranchSpec, RunResult, RunSummary, SampleResult
from pykit_bench.storage import RunStorage

__all__ = [
    "BenchRunner",
    "BranchSpec",
    "ComparisonResult",
    "ConfusionMatrix",
    "DatasetLoader",
    "DatasetManifest",
    "JsonReporter",
    "Label",
    "MarkdownReporter",
    "RunComparator",
    "RunResult",
    "RunStorage",
    "RunSummary",
    "Sample",
    "SampleResult",
    "ThresholdMetrics",
    "compute_metrics",
    "per_branch_metrics",
    "threshold_sweep",
]
