"""Report generation for bench runs."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pykit_bench.runner import RunResult


class MarkdownReporter:
    """Generate human-readable markdown report."""

    def generate(self, run_result: RunResult) -> str:
        """Create markdown with tables: overall, confusion matrix, per-branch, misclassified."""
        lines: list[str] = []
        m = run_result.metrics

        lines.append("═" * 65)
        lines.append(f"  BENCH RUN: {run_result.run_id}")
        n_pos = sum(1 for s in run_result.sample_results if s.is_positive)
        n_neg = len(run_result.sample_results) - n_pos
        tag = f" | Tag: {run_result.tag}" if run_result.tag else ""
        lines.append(
            f"  Samples: {len(run_result.sample_results)} ({n_pos} positive, {n_neg} negative)"
            f" | Threshold: {m.threshold:.2f}{tag}"
        )
        lines.append("═" * 65)
        lines.append("")

        # Overall
        lines.append("OVERALL ACCURACY")
        lines.append(
            f"  Precision: {m.precision:.3f}    Recall: {m.recall:.3f}"
            f"    F1: {m.f1:.3f}    Accuracy: {m.accuracy:.3f}"
        )
        lines.append("")

        # Confusion matrix
        cm = m.confusion
        lines.append(f"CONFUSION MATRIX (threshold={m.threshold:.2f})")
        lines.append(f"{'':17s}Predicted Positive    Predicted Negative")
        lines.append(f"  Actual Positive     {cm.tp:>4d} (TP)            {cm.fn:>4d} (FN)")
        lines.append(f"  Actual Negative     {cm.fp:>4d} (FP)            {cm.tn:>4d} (TN)")
        lines.append("")

        # Per-branch
        if run_result.per_branch:
            lines.append("PER-BRANCH BREAKDOWN")
            header = f"  {'Branch':<18s}{'F1':>6s}    {'Avg Pos Score':>13s}   {'Avg Neg Score':>13s}   {'Separation':>10s}"
            lines.append(header)
            lines.append("  " + "─" * 72)

            weakest_name = ""
            weakest_f1 = 1.1

            for name, bm in run_result.per_branch.items():
                # Compute avg scores per class
                pos_scores = [
                    s.branch_scores[name]
                    for s in run_result.sample_results
                    if s.is_positive and name in s.branch_scores
                ]
                neg_scores = [
                    s.branch_scores[name]
                    for s in run_result.sample_results
                    if not s.is_positive and name in s.branch_scores
                ]
                avg_pos = sum(pos_scores) / len(pos_scores) if pos_scores else 0.0
                avg_neg = sum(neg_scores) / len(neg_scores) if neg_scores else 0.0
                sep = avg_pos - avg_neg

                marker = ""
                if bm.f1 < weakest_f1:
                    weakest_f1 = bm.f1
                    weakest_name = name

                lines.append(
                    f"  {name:<18s}{bm.f1:>6.3f}    {avg_pos:>13.3f}   {avg_neg:>13.3f}   {sep:>10.3f}{marker}"
                )

            if weakest_name:
                lines.append("")
                lines.append(f"WEAKEST BRANCH: {weakest_name} (F1={weakest_f1:.3f})")
            lines.append("")

        # Misclassified
        misclassified = [
            s
            for s in run_result.sample_results
            if (s.overall_score >= m.threshold) != s.is_positive
        ]
        if misclassified:
            lines.append(f"MISCLASSIFIED SAMPLES ({len(misclassified)})")
            for s in misclassified:
                expected = "positive" if s.is_positive else "negative"
                predicted = "positive" if s.overall_score >= m.threshold else "negative"
                lines.append(
                    f"  {s.sample_id:<30s}  expected={expected}  predicted={predicted}"
                    f"  score={s.overall_score:.3f}"
                )
            lines.append("")

        return "\n".join(lines)


class JsonReporter:
    """Generate machine-readable JSON report."""

    def generate(self, run_result: RunResult) -> dict[str, object]:
        return json.loads(run_result.model_dump_json())
