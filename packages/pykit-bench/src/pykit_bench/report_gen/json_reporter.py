"""Canonical JSON report generation."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import io

    from pykit_bench.result import BenchRunResult


class JsonReporter:
    """Generates canonical JSON with $schema and version fields."""

    @property
    def name(self) -> str:
        return "json"

    def generate(self, writer: io.StringIO, result: BenchRunResult) -> None:
        """Write JSON report to *writer*."""
        data = result.model_dump(mode="json", by_alias=True)
        writer.write(json.dumps(data, indent=2, ensure_ascii=False))
