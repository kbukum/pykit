"""ASCII box-drawing table report for terminal display."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import io

    from pykit_bench.result import BenchRunResult


class TableReporter:
    """Generates ASCII box-drawing tables for terminal output."""

    @property
    def name(self) -> str:
        return "table"

    def generate(self, writer: io.StringIO, result: BenchRunResult) -> None:
        """Write ASCII table report to *writer*."""
        self._write_header(writer, result)
        self._write_metrics_table(writer, result)
        self._write_branches_table(writer, result)
        self._write_samples_table(writer, result)

    # ------------------------------------------------------------------

    def _write_header(self, w: io.StringIO, r: BenchRunResult) -> None:
        w.write(f"╔══ Benchmark Report: {r.id} ══╗\n")
        w.write(f"  Dataset:   {r.dataset.name}\n")
        w.write(f"  Samples:   {r.dataset.sample_count}\n")
        w.write(f"  Tag:       {r.tag or '—'}\n")
        w.write(f"  Duration:  {r.duration_ms} ms\n")
        w.write(f"  Timestamp: {r.timestamp.isoformat()}\n\n")

    def _write_metrics_table(self, w: io.StringIO, r: BenchRunResult) -> None:
        if not r.metrics:
            return
        # Determine column widths
        rows: list[tuple[str, str, str]] = []
        for m in r.metrics:
            details = ", ".join(f"{k}={v:.4f}" for k, v in m.values.items()) if m.values else ""
            rows.append((m.name, f"{m.value:.4f}", details))

        name_w = max(len("Metric"), *(len(r[0]) for r in rows))
        val_w = max(len("Value"), *(len(r[1]) for r in rows))
        det_w = max(len("Details"), *(len(r[2]) for r in rows)) if rows else len("Details")

        sep = f"├{'─' * (name_w + 2)}┼{'─' * (val_w + 2)}┼{'─' * (det_w + 2)}┤"
        top = f"┌{'─' * (name_w + 2)}┬{'─' * (val_w + 2)}┬{'─' * (det_w + 2)}┐"
        bot = f"└{'─' * (name_w + 2)}┴{'─' * (val_w + 2)}┴{'─' * (det_w + 2)}┘"

        w.write("Metrics:\n")
        w.write(top + "\n")
        w.write(f"│ {'Metric':<{name_w}} │ {'Value':<{val_w}} │ {'Details':<{det_w}} │\n")
        w.write(sep + "\n")
        for name, val, det in rows:
            w.write(f"│ {name:<{name_w}} │ {val:<{val_w}} │ {det:<{det_w}} │\n")
        w.write(bot + "\n\n")

    def _write_branches_table(self, w: io.StringIO, r: BenchRunResult) -> None:
        if not r.branches:
            return
        headers = ("Branch", "Tier", "Avg+", "Avg-", "Duration", "Errors")
        rows: list[tuple[str, ...]] = []
        for bname, br in r.branches.items():
            rows.append(
                (
                    bname,
                    str(br.tier),
                    f"{br.avg_score_positive:.4f}",
                    f"{br.avg_score_negative:.4f}",
                    f"{br.duration_ms}ms",
                    str(br.errors),
                )
            )

        widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
        top = "┌" + "┬".join(f"{'─' * (w + 2)}" for w in widths) + "┐"
        sep = "├" + "┼".join(f"{'─' * (w + 2)}" for w in widths) + "┤"
        bot = "└" + "┴".join(f"{'─' * (w + 2)}" for w in widths) + "┘"

        w.write("Branches:\n")
        w.write(top + "\n")
        w.write("│" + "│".join(f" {h:<{widths[i]}} " for i, h in enumerate(headers)) + "│\n")
        w.write(sep + "\n")
        for row in rows:
            w.write("│" + "│".join(f" {row[i]:<{widths[i]}} " for i in range(len(headers))) + "│\n")
        w.write(bot + "\n\n")

    def _write_samples_table(self, w: io.StringIO, r: BenchRunResult) -> None:
        if not r.samples:
            return
        max_samples = 30
        headers = ("ID", "Label", "Predicted", "Score", "OK")
        rows: list[tuple[str, ...]] = []
        for s in r.samples[:max_samples]:
            rows.append(
                (
                    s.id,
                    s.label,
                    s.predicted,
                    f"{s.score:.4f}",
                    "✓" if s.correct else "✗",
                )
            )

        widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
        top = "┌" + "┬".join(f"{'─' * (w + 2)}" for w in widths) + "┐"
        sep = "├" + "┼".join(f"{'─' * (w + 2)}" for w in widths) + "┤"
        bot = "└" + "┴".join(f"{'─' * (w + 2)}" for w in widths) + "┘"

        title = "Samples"
        if len(r.samples) > max_samples:
            title += f" (showing {max_samples} of {len(r.samples)})"
        w.write(f"{title}:\n")
        w.write(top + "\n")
        w.write("│" + "│".join(f" {h:<{widths[i]}} " for i, h in enumerate(headers)) + "│\n")
        w.write(sep + "\n")
        for row in rows:
            w.write("│" + "│".join(f" {row[i]:<{widths[i]}} " for i in range(len(headers))) + "│\n")
        w.write(bot + "\n\n")
