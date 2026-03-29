"""Run comparison and regression detection using new result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pykit_bench.result import BenchRunResult


@dataclass
class MetricChange:
    """A single metric's change between runs."""

    name: str
    old_value: float
    new_value: float
    delta: float
    improved: bool
    significant: bool


@dataclass
class RunDiff:
    """Differences between two benchmark runs."""

    base_id: str
    target_id: str
    changes: list[MetricChange] = field(default_factory=list)
    fixed: list[str] = field(default_factory=list)
    regressed: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Human-readable comparison summary."""
        lines = [f"Comparison: {self.base_id} → {self.target_id}"]
        for c in self.changes:
            icon = "✅" if c.improved else "⚠️"
            sign = "+" if c.delta >= 0 else ""
            lines.append(f"  {icon} {c.name}: {c.old_value:.4f} → {c.new_value:.4f} ({sign}{c.delta:.4f})")
        if self.fixed:
            lines.append(f"  Fixed: {len(self.fixed)} samples")
        if self.regressed:
            lines.append(f"  Regressed: {len(self.regressed)} samples")
        return "\n".join(lines)

    def has_regression(self) -> bool:
        """Returns True if any metric decreased significantly."""
        return any(not c.improved and c.significant for c in self.changes)


class BenchRunComparator:
    """Compares two benchmark runs to detect improvements and regressions."""

    def __init__(self, *, change_threshold: float = 0.01) -> None:
        self._threshold = change_threshold

    def compare(self, base: BenchRunResult, target: BenchRunResult) -> RunDiff:
        """Compare two runs, returning differences."""
        changes: list[MetricChange] = []

        # Compare top-level metrics
        base_metrics = {m.name: m for m in base.metrics}
        for tm in target.metrics:
            bm = base_metrics.get(tm.name)
            if bm is None:
                continue
            delta = tm.value - bm.value
            significant = abs(delta) >= self._threshold
            changes.append(
                MetricChange(
                    name=tm.name,
                    old_value=bm.value,
                    new_value=tm.value,
                    delta=delta,
                    improved=delta > 0,
                    significant=significant,
                )
            )
            # Compare sub-values
            for key, new_val in tm.values.items():
                old_val = bm.values.get(key)
                if old_val is not None:
                    d = new_val - old_val
                    if abs(d) >= self._threshold:
                        changes.append(
                            MetricChange(
                                name=f"{tm.name}.{key}",
                                old_value=old_val,
                                new_value=new_val,
                                delta=d,
                                improved=d > 0,
                                significant=abs(d) >= self._threshold,
                            )
                        )

        # Per-sample correctness changes
        base_correct = {s.id: s.correct for s in base.samples}
        fixed: list[str] = []
        regressed: list[str] = []
        for ts in target.samples:
            was_correct = base_correct.get(ts.id)
            if was_correct is not None:
                if not was_correct and ts.correct:
                    fixed.append(ts.id)
                elif was_correct and not ts.correct:
                    regressed.append(ts.id)

        return RunDiff(
            base_id=base.id,
            target_id=target.id,
            changes=changes,
            fixed=fixed,
            regressed=regressed,
        )
