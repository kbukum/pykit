"""Storage protocol and file-based implementation for bench results."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol

from pykit_bench.result import BenchRunResult, BenchRunSummary

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class ListOptions:
    """Options for listing stored results."""

    limit: int = 100
    tag: str | None = None
    dataset: str | None = None


class BenchRunStorage(Protocol):
    """Abstraction for storing/retrieving benchmark results."""

    def save(self, result: BenchRunResult) -> str: ...
    def load(self, run_id: str) -> BenchRunResult: ...
    def latest(self) -> BenchRunResult: ...
    def list_runs(self, opts: ListOptions | None = None) -> list[BenchRunSummary]: ...


class FileRunStorage:
    """File-based storage for bench results."""

    def __init__(self, results_dir: Path) -> None:
        self._dir = results_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, result: BenchRunResult) -> str:
        path = self._dir / f"{result.id}.json"
        path.write_text(result.model_dump_json(indent=2, by_alias=True), encoding="utf-8")
        return result.id

    def load(self, run_id: str) -> BenchRunResult:
        path = self._dir / f"{run_id}.json"
        if not path.exists():
            msg = f"Run not found: {run_id}"
            raise FileNotFoundError(msg)
        data = json.loads(path.read_text(encoding="utf-8"))
        return BenchRunResult.model_validate(data)

    def latest(self) -> BenchRunResult:
        summaries = self.list_runs(ListOptions(limit=1))
        if not summaries:
            msg = "No runs found"
            raise FileNotFoundError(msg)
        return self.load(summaries[0].id)

    def list_runs(self, opts: ListOptions | None = None) -> list[BenchRunSummary]:
        if opts is None:
            opts = ListOptions()
        if not self._dir.exists():
            return []

        summaries: list[BenchRunSummary] = []
        for path in self._dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                result = BenchRunResult.model_validate(data)
            except Exception:
                continue

            if opts.tag and result.tag != opts.tag:
                continue
            if opts.dataset and result.dataset.name != opts.dataset:
                continue

            f1 = 0.0
            for m in result.metrics:
                if "f1" in m.values:
                    f1 = m.values["f1"]
                    break
                if m.name in ("classification", "multi_class_classification"):
                    f1 = m.value
                    break

            summaries.append(
                BenchRunSummary(
                    id=result.id,
                    timestamp=result.timestamp,
                    tag=result.tag,
                    dataset=result.dataset.name,
                    f1=f1,
                )
            )

        summaries.sort(key=lambda s: s.timestamp, reverse=True)
        if opts.limit > 0:
            summaries = summaries[: opts.limit]
        return summaries

    @staticmethod
    def generate_run_id(name: str) -> str:
        """Generate a timestamped run ID."""
        now = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
        return f"{name}-{now}"
