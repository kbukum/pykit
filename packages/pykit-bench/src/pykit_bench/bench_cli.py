"""CLI utilities for bench operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pykit_bench.report_gen.markdown import MarkdownReporter
from pykit_bench.run_comparator import BenchRunComparator
from pykit_bench.run_storage import FileRunStorage, ListOptions

if TYPE_CHECKING:
    import io
    from pathlib import Path

    from pykit_bench.result import BenchRunResult


class BenchCliRunner:
    """CLI runner for bench operations."""

    def __init__(self, results_dir: Path) -> None:
        self._storage = FileRunStorage(results_dir)

    def show_latest(self, writer: io.StringIO) -> None:
        result = self._storage.latest()
        self._show_detail(writer, result)

    def show_run(self, writer: io.StringIO, run_id: str) -> None:
        result = self._storage.load(run_id)
        self._show_detail(writer, result)

    def _show_detail(self, writer: io.StringIO, result: BenchRunResult) -> None:
        reporter = MarkdownReporter()
        reporter.generate(writer, result)

    def compare_runs(self, writer: io.StringIO, base_id: str, target_id: str) -> None:
        base = self._storage.load(base_id)
        target = self._storage.load(target_id)
        comparator = BenchRunComparator()
        diff = comparator.compare(base, target)
        writer.write(diff.summary())
        writer.write("\n")

    def compare_latest(self, writer: io.StringIO) -> None:
        runs = self._storage.list_runs(ListOptions(limit=2))
        if len(runs) < 2:
            raise ValueError("Need at least 2 runs to compare")
        self.compare_runs(writer, runs[1].id, runs[0].id)

    def list_runs(self, writer: io.StringIO, opts: ListOptions | None = None) -> None:
        if opts is None:
            opts = ListOptions()
        runs = self._storage.list_runs(opts)
        if not runs:
            writer.write("No runs found.\n")
            return
        writer.write(f"{'ID':<40} {'Timestamp':<24} {'Tag':<15} {'F1':>6}\n")
        writer.write("-" * 85 + "\n")
        for r in runs:
            ts = r.timestamp.isoformat()
            writer.write(f"{r.id:<40} {ts:<24} {r.tag:<15} {r.f1:>6.4f}\n")
        writer.write(f"\nTotal: {len(runs)} run(s)\n")
