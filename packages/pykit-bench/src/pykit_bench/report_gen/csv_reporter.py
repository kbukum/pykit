"""Flat CSV report generation."""

from __future__ import annotations

import csv
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import io

    from pykit_bench.result import BenchRunResult


class CsvReporter:
    """Generates a flat CSV: metric_name, value, details columns."""

    @property
    def name(self) -> str:
        return "csv"

    def generate(self, writer: io.StringIO, result: BenchRunResult) -> None:
        """Write CSV report to *writer*."""
        csv_writer = csv.writer(writer)
        csv_writer.writerow(["metric_name", "value", "details"])

        for m in result.metrics:
            details = "; ".join(f"{k}={v:.4f}" for k, v in m.values.items()) if m.values else ""
            csv_writer.writerow([m.name, f"{m.value:.4f}", details])

            # Expand sub-values as separate rows
            for key, val in m.values.items():
                csv_writer.writerow([f"{m.name}.{key}", f"{val:.4f}", ""])
