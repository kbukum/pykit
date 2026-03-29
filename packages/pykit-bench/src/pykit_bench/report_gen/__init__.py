"""pykit_bench.report_gen — Multi-format report generation."""

from __future__ import annotations

from pykit_bench.report_gen.base import Reporter
from pykit_bench.report_gen.csv_reporter import CsvReporter
from pykit_bench.report_gen.json_reporter import JsonReporter
from pykit_bench.report_gen.junit import JUnitReporter
from pykit_bench.report_gen.markdown import MarkdownReporter
from pykit_bench.report_gen.table import TableReporter
from pykit_bench.report_gen.vegalite import VegaLiteReporter, vegalite_specs

__all__ = [
    "CsvReporter",
    "JUnitReporter",
    "JsonReporter",
    "MarkdownReporter",
    "Reporter",
    "TableReporter",
    "VegaLiteReporter",
    "vegalite_specs",
]
