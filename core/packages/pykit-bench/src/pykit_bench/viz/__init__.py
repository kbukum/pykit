"""SVG chart rendering for benchmark results."""

from __future__ import annotations

from pykit_bench.viz.calibration import render_calibration
from pykit_bench.viz.comparison import render_comparison
from pykit_bench.viz.confusion import render_confusion
from pykit_bench.viz.distribution import render_distribution
from pykit_bench.viz.render import RenderOptions, render_all
from pykit_bench.viz.roc import render_roc

__all__ = [
    "RenderOptions",
    "render_all",
    "render_calibration",
    "render_comparison",
    "render_confusion",
    "render_distribution",
    "render_roc",
]
