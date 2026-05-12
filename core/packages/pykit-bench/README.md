# pykit-bench

Generic accuracy benchmarking framework for ML model evaluation with pluggable metrics, dataset loading, reporting, and visualization.

## Installation

```bash
pip install pykit-bench
# or
uv add pykit-bench
```

## Quick Start

```python
from pathlib import Path
from pykit_bench import (
    BenchRunner, BranchSpec, DatasetLoader, Label,
    compute_metrics, MarkdownReporter,
)

# Load a labeled test dataset
loader = DatasetLoader(Path("tests/dataset"))

# Register evaluation branches
runner = BenchRunner(loader, positive_label=Label.POSITIVE)
runner.register_branch("model_v1", my_model_fn, tier=1)

# Run benchmark and print report
result = await runner.run(tag="nightly", threshold=0.5)
runner.report(result, format="markdown")

# Or compute metrics directly
metrics = compute_metrics(
    scores=[0.9, 0.1, 0.8, 0.3],
    labels=[True, False, True, False],
    threshold=0.5,
)
print(f"F1: {metrics.f1:.3f}, Accuracy: {metrics.accuracy:.3f}")
```

## Key Components

- **BenchRunner** — Orchestrates evaluation branches against a labeled dataset with async execution
- **DatasetLoader / DatasetManifest / Sample** — Load and validate test datasets from manifest.json + files on disk
- **compute_metrics()** — Compute precision, recall, F1, accuracy at a threshold
- **threshold_sweep()** — Evaluate metrics across multiple thresholds
- **per_branch_metrics()** — Compare multiple model branches at a given threshold
- **ConfusionMatrix / ThresholdMetrics** — Result types for binary classification metrics
- **Metric[L] Protocol** — Pluggable metric interface with built-in classification, probability, regression, matching, and ranking metrics
- **MarkdownReporter / JsonReporter** — Report generation in Markdown and JSON formats
- **RunStorage / RunComparator** — Persist and compare benchmark runs over time
- **BranchSpec / SampleResult / RunResult / RunSummary** — Configuration and result data types

## Dependencies

- `pydantic` — Data validation and serialization

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
