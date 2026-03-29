"""Bench runner — orchestrates the complete benchmark lifecycle."""

from __future__ import annotations

import asyncio
import io
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, TypeVar

from pykit_bench.result import (
    BenchRunResult,
    BenchSampleResult,
    BranchResult,
    DatasetInfo,
    MetricResult,
)
from pykit_bench.schema import SCHEMA_URL, SCHEMA_VERSION
from pykit_bench.types import BenchSample, Prediction, ScoredSample

if TYPE_CHECKING:
    from pykit_bench.dataset_loader import GenericDatasetLoader
    from pykit_bench.evaluator import Evaluator
    from pykit_bench.metric.base import MetricSuite
    from pykit_bench.report_gen.base import Reporter
    from pykit_bench.run_comparator import BenchRunComparator
    from pykit_bench.run_storage import BenchRunStorage

L = TypeVar("L")


@dataclass
class RunOptions:
    """Options for configuring a benchmark run."""

    concurrency: int = 4
    timeout_secs: float = 30.0
    tag: str = "default"
    fail_on_regression: bool = False
    targets: dict[str, float] = field(default_factory=dict)


@dataclass
class BranchConfig[L]:
    """A registered evaluation branch."""

    name: str
    evaluator: Evaluator[L]
    tier: int = 0


class BenchRunnerV2[L]:
    """Enhanced bench runner orchestrating evaluation, metrics, storage, reporting."""

    def __init__(self) -> None:
        self._branches: list[BranchConfig[L]] = []
        self._metrics: MetricSuite[L] | None = None
        self._storage: BenchRunStorage | None = None
        self._reporters: list[Reporter] = []
        self._comparator: BenchRunComparator | None = None

    def register(self, name: str, evaluator: Evaluator[L], tier: int = 0) -> BenchRunnerV2[L]:
        self._branches.append(BranchConfig(name=name, evaluator=evaluator, tier=tier))
        return self

    def with_metrics(self, suite: MetricSuite[L]) -> BenchRunnerV2[L]:
        self._metrics = suite
        return self

    def with_storage(self, storage: BenchRunStorage) -> BenchRunnerV2[L]:
        self._storage = storage
        return self

    def with_reporter(self, reporter: Reporter) -> BenchRunnerV2[L]:
        self._reporters.append(reporter)
        return self

    def with_comparator(self, comparator: BenchRunComparator) -> BenchRunnerV2[L]:
        self._comparator = comparator
        return self

    async def run(
        self,
        loader: GenericDatasetLoader[L],
        opts: RunOptions | None = None,
    ) -> BenchRunResult:
        if opts is None:
            opts = RunOptions()

        start = time.monotonic()

        # 1. Load dataset
        samples = loader.all()
        label_dist = Counter(str(s.label) for s in samples)
        dataset_info = DatasetInfo(
            name=opts.tag,
            sample_count=len(samples),
            label_distribution=dict(label_dist),
        )

        # 2. Evaluate each branch
        semaphore = asyncio.Semaphore(opts.concurrency)
        branch_results: dict[str, BranchResult] = {}
        all_scored: list[ScoredSample[L]] = []
        sample_results: list[BenchSampleResult] = []

        for branch in self._branches:
            correct_count = 0
            total = 0
            error_count = 0
            pos_scores: list[float] = []
            neg_scores: list[float] = []
            branch_start = time.monotonic()

            async def _eval_sample(
                sample: BenchSample[L],
                _branch: BranchConfig[L] = branch,
            ) -> tuple[Prediction[L] | None, bool]:
                async with semaphore:
                    try:
                        pred = await asyncio.wait_for(
                            _branch.evaluator.evaluate(sample.input),
                            timeout=opts.timeout_secs,
                        )
                        is_correct = str(pred.label) == str(sample.label)
                        return pred, is_correct
                    except TimeoutError:
                        return None, False
                    except Exception:
                        return None, False

            tasks = [_eval_sample(s) for s in samples]
            results = await asyncio.gather(*tasks)

            for sample, (pred, is_correct) in zip(samples, results, strict=False):
                total += 1
                if pred is not None:
                    if is_correct:
                        correct_count += 1
                        pos_scores.append(pred.score)
                    else:
                        neg_scores.append(pred.score)
                    sample_results.append(
                        BenchSampleResult(
                            id=sample.id,
                            label=str(sample.label),
                            predicted=str(pred.label),
                            correct=is_correct,
                            score=pred.score,
                            branch_scores={branch.name: pred.score},
                        )
                    )
                    all_scored.append(ScoredSample(sample=sample, prediction=pred))
                else:
                    error_count += 1
                    sample_results.append(
                        BenchSampleResult(
                            id=sample.id,
                            label=str(sample.label),
                            predicted="",
                            correct=False,
                            score=0.0,
                            branch_scores={},
                            error="evaluation failed",
                        )
                    )

            branch_elapsed_ms = int((time.monotonic() - branch_start) * 1000)
            accuracy = correct_count / total if total > 0 else 0.0
            avg_pos = sum(pos_scores) / len(pos_scores) if pos_scores else 0.0
            avg_neg = sum(neg_scores) / len(neg_scores) if neg_scores else 0.0

            branch_results[branch.name] = BranchResult(
                name=branch.name,
                tier=branch.tier,
                metrics={"accuracy": accuracy},
                avg_score_positive=avg_pos,
                avg_score_negative=avg_neg,
                duration_ms=branch_elapsed_ms,
                errors=error_count,
            )

        # 3. Compute metrics
        metric_results: list[MetricResult] = []
        if self._metrics is not None:
            metric_results = self._metrics.compute(all_scored)

        # 4. Build result
        elapsed_ms = int((time.monotonic() - start) * 1000)
        now = datetime.now(tz=UTC)
        run_id = f"{opts.tag}_{now.strftime('%Y%m%d_%H%M%S')}"

        bench_result = BenchRunResult(
            id=run_id,
            schema_url=SCHEMA_URL,
            version=SCHEMA_VERSION,
            timestamp=now,
            tag=opts.tag,
            duration_ms=elapsed_ms,
            dataset=dataset_info,
            metrics=metric_results,
            branches=branch_results,
            samples=sample_results,
            curves={},
        )

        # 5. Store
        if self._storage is not None:
            self._storage.save(bench_result)

        # 6. Reports
        for reporter in self._reporters:
            try:
                writer = io.StringIO()
                reporter.generate(writer, bench_result)
            except Exception:
                pass

        # 7. Compare with previous
        if self._comparator is not None and self._storage is not None:
            try:
                prev = self._storage.latest()
                if prev.id != bench_result.id:
                    diff = self._comparator.compare(prev, bench_result)
                    if opts.fail_on_regression and diff.has_regression():
                        raise RuntimeError(f"Regression detected:\n{diff.summary()}")
            except FileNotFoundError:
                pass

        return bench_result
