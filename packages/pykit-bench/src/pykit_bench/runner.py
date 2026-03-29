"""Bench runner — orchestrate branches against a dataset and compute metrics."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from pykit_bench.metrics import ThresholdMetrics, compute_metrics, per_branch_metrics
from pykit_bench.report import MarkdownReporter

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from pykit_bench.dataset import DatasetLoader
    from pykit_bench.storage import RunStorage


@dataclass
class BranchSpec:
    """Registration for a bench-able analysis branch."""

    name: str
    func: Callable[[bytes, dict[str, object] | None], Awaitable[float]]
    tier: int = 1


@dataclass
class SampleResult:
    """Result of running all branches on a single sample."""

    sample_id: str
    label: str
    is_positive: bool
    overall_score: float
    branch_scores: dict[str, float] = field(default_factory=dict)
    processing_ms: int = 0


class RunSummary(BaseModel):
    """Lightweight summary of a saved run."""

    run_id: str
    timestamp: datetime
    tag: str = ""
    dataset_name: str = ""
    f1: float = 0.0
    accuracy: float = 0.0
    sample_count: int = 0


class RunResult(BaseModel):
    """Complete result of a bench run."""

    run_id: str
    timestamp: datetime
    tag: str = ""
    config: dict[str, object] = Field(default_factory=dict)
    dataset_name: str = ""
    sample_results: list[SampleResult] = Field(default_factory=list)
    metrics: ThresholdMetrics = Field(
        default_factory=lambda: ThresholdMetrics(
            threshold=0.5, precision=0.0, recall=0.0, f1=0.0, accuracy=0.0, fpr=0.0
        )
    )
    per_branch: dict[str, ThresholdMetrics] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True


class BenchRunner:
    """Run analysis branches against a dataset and compute metrics."""

    def __init__(
        self,
        dataset_loader: DatasetLoader,
        positive_label: str,
        branches: list[BranchSpec] | None = None,
        storage: RunStorage | None = None,
    ) -> None:
        self._loader = dataset_loader
        self._positive_label = positive_label
        self._branches: list[BranchSpec] = list(branches) if branches else []
        self._storage = storage

    def register_branch(self, name: str, func: Callable[..., Awaitable[float]], tier: int = 1) -> None:
        """Register an analysis branch for benchmarking."""
        self._branches.append(BranchSpec(name=name, func=func, tier=tier))

    async def run(self, tag: str = "", threshold: float = 0.5) -> RunResult:
        """Run all branches on all samples, compute metrics, save results."""
        manifest = self._loader.load()
        run_name = manifest.name if manifest.name else "bench"

        run_id = (
            self._storage.generate_run_id(run_name)
            if self._storage
            else f"{run_name}-{datetime.now(tz=UTC).strftime('%Y%m%d-%H%M%S')}"
        )

        sample_results: list[SampleResult] = []
        all_scores: list[float] = []
        all_labels: list[bool] = []
        branch_scores_map: dict[str, list[float]] = {b.name: [] for b in self._branches}

        for sample in manifest.samples:
            content = self._loader.get_content(sample)
            is_positive = sample.label == self._positive_label

            start = time.monotonic()
            branch_scores: dict[str, float] = {}

            for branch in self._branches:
                try:
                    score = await branch.func(content, None)
                    branch_scores[branch.name] = score
                    branch_scores_map[branch.name].append(score)
                except Exception:
                    branch_scores[branch.name] = 0.0
                    branch_scores_map[branch.name].append(0.0)

            elapsed_ms = int((time.monotonic() - start) * 1000)

            # Overall score = weighted average, giving more weight to branches
            # that show stronger signal (further from 0.5 = more decisive)
            weighted_sum = 0.0
            weight_total = 0.0
            for _bname, bscore in branch_scores.items():
                # Weight by decisiveness: how far the score is from 0.5
                decisiveness = abs(bscore - 0.5) + 0.1  # minimum weight 0.1
                weighted_sum += bscore * decisiveness
                weight_total += decisiveness
            overall = weighted_sum / weight_total if weight_total > 0 else 0.0

            all_scores.append(overall)
            all_labels.append(is_positive)

            sample_results.append(
                SampleResult(
                    sample_id=sample.id,
                    label=sample.label,
                    is_positive=is_positive,
                    overall_score=round(overall, 4),
                    branch_scores={k: round(v, 4) for k, v in branch_scores.items()},
                    processing_ms=elapsed_ms,
                )
            )

        # Compute metrics
        metrics = compute_metrics(all_scores, all_labels, threshold)
        branch_metrics = per_branch_metrics(branch_scores_map, all_labels, threshold)

        result = RunResult(
            run_id=run_id,
            timestamp=datetime.now(tz=UTC),
            tag=tag,
            config={"threshold": threshold, "branches": [b.name for b in self._branches]},
            dataset_name=manifest.name,
            sample_results=sample_results,
            metrics=metrics,
            per_branch=branch_metrics,
        )

        if self._storage:
            self._storage.save(result)

        return result

    def report(self, result: RunResult, format: str = "markdown") -> None:
        """Print a report to stdout."""
        if format == "markdown":
            print(MarkdownReporter().generate(result))
        else:
            import json

            from pykit_bench.report import JsonReporter

            print(json.dumps(JsonReporter().generate(result), indent=2, default=str))
