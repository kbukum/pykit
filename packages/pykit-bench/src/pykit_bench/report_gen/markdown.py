"""GFM Markdown report generation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import io

    from pykit_bench.result import BenchRunResult


class MarkdownReporter:
    """Generates GitHub-Flavored Markdown tables from benchmark results."""

    @property
    def name(self) -> str:
        return "markdown"

    def generate(self, writer: io.StringIO, result: BenchRunResult) -> None:
        """Write a full Markdown report to *writer*."""
        self._write_summary(writer, result)
        self._write_metrics(writer, result)
        self._write_confusion_matrix(writer, result)
        self._write_branches(writer, result)
        self._write_samples(writer, result)

    # ------------------------------------------------------------------

    def _write_summary(self, w: io.StringIO, r: BenchRunResult) -> None:
        w.write(f"# Benchmark Report: {r.id}\n\n")
        w.write("| Field | Value |\n|---|---|\n")
        w.write(f"| **Run ID** | `{r.id}` |\n")
        w.write(f"| **Timestamp** | {r.timestamp.isoformat()} |\n")
        w.write(f"| **Tag** | {r.tag or '—'} |\n")
        w.write(f"| **Dataset** | {r.dataset.name} |\n")
        w.write(f"| **Samples** | {r.dataset.sample_count} |\n")
        w.write(f"| **Duration** | {r.duration_ms} ms |\n")
        w.write(f"| **Version** | {r.version} |\n\n")

    def _write_metrics(self, w: io.StringIO, r: BenchRunResult) -> None:
        if not r.metrics:
            return
        w.write("## Metrics\n\n")
        w.write("| Metric | Value | Details |\n|---|---|---|\n")
        for m in r.metrics:
            details = ", ".join(f"{k}={v:.4f}" for k, v in m.values.items()) if m.values else "—"
            w.write(f"| {m.name} | {m.value:.4f} | {details} |\n")
        w.write("\n")

    def _write_confusion_matrix(self, w: io.StringIO, r: BenchRunResult) -> None:
        cm = self._find_confusion_matrix(r)
        if cm is None:
            return
        labels: list[str] = cm.get("labels", [])
        matrix: list[list[int]] = cm.get("matrix", [])
        if not labels or not matrix:
            return
        w.write("## Confusion Matrix\n\n")
        w.write("| |" + "|".join(f" **{label}** " for label in labels) + "|\n")
        w.write("|---|" + "|".join("---" for _ in labels) + "|\n")
        for i, row in enumerate(matrix):
            cells = "|".join(f" {v} " for v in row)
            w.write(f"| **{labels[i]}** |{cells}|\n")
        w.write("\n")

    def _write_branches(self, w: io.StringIO, r: BenchRunResult) -> None:
        if not r.branches:
            return
        w.write("## Branches\n\n")
        w.write("| Branch | Tier | Avg+ | Avg- | Duration | Errors |\n")
        w.write("|---|---|---|---|---|---|\n")
        for name, br in r.branches.items():
            w.write(
                f"| {name} | {br.tier} | {br.avg_score_positive:.4f} "
                f"| {br.avg_score_negative:.4f} | {br.duration_ms} ms "
                f"| {br.errors} |\n"
            )
        w.write("\n")

    def _write_samples(self, w: io.StringIO, r: BenchRunResult) -> None:
        if not r.samples:
            return
        max_samples = 50
        w.write("## Samples")
        if len(r.samples) > max_samples:
            w.write(f" (showing {max_samples} of {len(r.samples)})")
        w.write("\n\n")
        w.write("| ID | Label | Predicted | Score | Correct |\n")
        w.write("|---|---|---|---|---|\n")
        for s in r.samples[:max_samples]:
            icon = "✅" if s.correct else "❌"
            w.write(f"| {s.id} | {s.label} | {s.predicted} | {s.score:.4f} | {icon} |\n")
        w.write("\n")

    # ------------------------------------------------------------------

    @staticmethod
    def _find_confusion_matrix(r: BenchRunResult) -> dict[str, Any] | None:
        """Extract confusion matrix from curves or metric detail."""
        if "confusion_matrix" in r.curves:
            return r.curves["confusion_matrix"]  # type: ignore[return-value]
        for m in r.metrics:
            if m.detail and isinstance(m.detail, dict) and "matrix" in m.detail:
                return m.detail  # type: ignore[return-value]
        return None
