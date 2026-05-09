"""Reporter protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import io

    from pykit_bench.result import BenchRunResult


class Reporter(Protocol):
    """Protocol for generating reports from benchmark results."""

    @property
    def name(self) -> str:
        """Return the reporter name."""

    def generate(self, writer: io.StringIO, result: BenchRunResult) -> None:
        """Write a report for the given benchmark result."""
