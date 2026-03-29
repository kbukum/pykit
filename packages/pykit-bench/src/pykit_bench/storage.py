"""Persistent storage for bench run results."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from pykit_bench.runner import RunResult, RunSummary


class RunStorage:
    """Persist and retrieve bench run results."""

    def __init__(self, results_dir: Path) -> None:
        self._dir = results_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, run_result: RunResult) -> str:
        """Save run to results/<run-id>.json, return run_id."""
        path = self._dir / f"{run_result.run_id}.json"
        path.write_text(run_result.model_dump_json(indent=2), encoding="utf-8")
        return run_result.run_id

    def load(self, run_id: str) -> RunResult:
        """Load a run by its ID."""
        from pykit_bench.runner import RunResult

        path = self._dir / f"{run_id}.json"
        if not path.exists():
            msg = f"Run not found: {run_id}"
            raise FileNotFoundError(msg)
        data = json.loads(path.read_text(encoding="utf-8"))
        return RunResult.model_validate(data)

    def latest(self) -> RunResult:
        """Load the most recent run."""
        runs = sorted(self._dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not runs:
            msg = f"No runs found in {self._dir}"
            raise FileNotFoundError(msg)
        return self.load(runs[0].stem)

    def list_runs(self, media_type: str | None = None) -> list[RunSummary]:
        """List all saved runs, optionally filtered by media type."""
        from pykit_bench.runner import RunSummary

        summaries: list[RunSummary] = []
        for path in sorted(self._dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            data = json.loads(path.read_text(encoding="utf-8"))
            run_id = data.get("run_id", path.stem)
            dataset = data.get("dataset_name", "")
            if media_type and media_type not in dataset and media_type not in run_id:
                continue
            summaries.append(
                RunSummary(
                    run_id=run_id,
                    timestamp=datetime.fromisoformat(data["timestamp"]),
                    tag=data.get("tag", ""),
                    dataset_name=dataset,
                    f1=data.get("metrics", {}).get("f1", 0.0),
                    accuracy=data.get("metrics", {}).get("accuracy", 0.0),
                    sample_count=len(data.get("sample_results", [])),
                )
            )
        return summaries

    def generate_run_id(self, name: str) -> str:
        """Generate a timestamped run ID."""
        ts = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
        return f"{name}-{ts}"
