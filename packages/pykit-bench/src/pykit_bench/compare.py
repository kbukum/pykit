"""Compare two bench runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pykit_bench.runner import RunResult


@dataclass
class BranchDiff:
    """Difference in metrics for a single branch between two runs."""

    branch: str
    f1_before: float
    f1_after: float
    f1_delta: float
    precision_delta: float
    recall_delta: float
    improved: bool


@dataclass
class ComparisonResult:
    """Result of comparing two bench runs."""

    run_a_id: str
    run_b_id: str
    f1_before: float
    f1_after: float
    f1_delta: float
    accuracy_before: float
    accuracy_after: float
    accuracy_delta: float
    branch_diffs: list[BranchDiff] = field(default_factory=list)
    fixed_samples: list[str] = field(default_factory=list)
    regressed_samples: list[str] = field(default_factory=list)

    @property
    def improved(self) -> bool:
        return self.f1_delta > 0

    def summary(self) -> str:
        """Human-readable comparison summary."""
        lines: list[str] = []
        direction = "📈 IMPROVED" if self.improved else "📉 REGRESSED"
        lines.append(f"COMPARISON: {self.run_a_id} → {self.run_b_id}  {direction}")
        lines.append(f"  Overall F1:  {self.f1_before:.3f} → {self.f1_after:.3f} ({self.f1_delta:+.3f})")
        lines.append(
            f"  Accuracy:    {self.accuracy_before:.3f} → {self.accuracy_after:.3f}"
            f" ({self.accuracy_delta:+.3f})"
        )
        lines.append("")

        if self.branch_diffs:
            lines.append("PER-BRANCH CHANGES")
            for bd in self.branch_diffs:
                marker = "✅" if bd.improved else "❌" if bd.f1_delta < 0 else "—"
                lines.append(
                    f"  {marker} {bd.branch:<18s} F1: {bd.f1_before:.3f} → {bd.f1_after:.3f} ({bd.f1_delta:+.3f})"
                )
            lines.append("")

        if self.fixed_samples:
            lines.append(f"FIXED ({len(self.fixed_samples)} samples now correct)")
            for sid in self.fixed_samples:
                lines.append(f"  ✅ {sid}")
            lines.append("")

        if self.regressed_samples:
            lines.append(f"REGRESSIONS ({len(self.regressed_samples)} samples now wrong)")
            for sid in self.regressed_samples:
                lines.append(f"  ❌ {sid}")

        return "\n".join(lines)


class RunComparator:
    """Compare two bench runs."""

    def compare(self, run_a: RunResult, run_b: RunResult) -> ComparisonResult:
        """Diff metrics, show improvements/regressions, fixed/new misclassifications."""
        ma = run_a.metrics
        mb = run_b.metrics
        threshold = mb.threshold

        # Per-branch diffs
        branch_diffs: list[BranchDiff] = []
        all_branches = set(run_a.per_branch.keys()) | set(run_b.per_branch.keys())
        for branch in sorted(all_branches):
            f1_a = run_a.per_branch[branch].f1 if branch in run_a.per_branch else 0.0
            f1_b = run_b.per_branch[branch].f1 if branch in run_b.per_branch else 0.0
            prec_a = run_a.per_branch[branch].precision if branch in run_a.per_branch else 0.0
            prec_b = run_b.per_branch[branch].precision if branch in run_b.per_branch else 0.0
            rec_a = run_a.per_branch[branch].recall if branch in run_a.per_branch else 0.0
            rec_b = run_b.per_branch[branch].recall if branch in run_b.per_branch else 0.0
            delta = round(f1_b - f1_a, 4)
            branch_diffs.append(
                BranchDiff(
                    branch=branch,
                    f1_before=f1_a,
                    f1_after=f1_b,
                    f1_delta=delta,
                    precision_delta=round(prec_b - prec_a, 4),
                    recall_delta=round(rec_b - rec_a, 4),
                    improved=delta > 0,
                )
            )

        # Find fixed/regressed samples
        a_results = {s.sample_id: s for s in run_a.sample_results}
        b_results = {s.sample_id: s for s in run_b.sample_results}
        common = set(a_results.keys()) & set(b_results.keys())

        fixed: list[str] = []
        regressed: list[str] = []
        for sid in sorted(common):
            sa = a_results[sid]
            sb = b_results[sid]
            a_correct = (sa.overall_score >= threshold) == sa.is_positive
            b_correct = (sb.overall_score >= threshold) == sb.is_positive
            if not a_correct and b_correct:
                fixed.append(sid)
            elif a_correct and not b_correct:
                regressed.append(sid)

        return ComparisonResult(
            run_a_id=run_a.run_id,
            run_b_id=run_b.run_id,
            f1_before=ma.f1,
            f1_after=mb.f1,
            f1_delta=round(mb.f1 - ma.f1, 4),
            accuracy_before=ma.accuracy,
            accuracy_after=mb.accuracy,
            accuracy_delta=round(mb.accuracy - ma.accuracy, 4),
            branch_diffs=branch_diffs,
            fixed_samples=fixed,
            regressed_samples=regressed,
        )
