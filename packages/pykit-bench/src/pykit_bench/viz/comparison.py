"""Branch comparison bar chart SVG renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pykit_bench.viz.svg_builder import SvgBuilder, color_at, draw_axes

if TYPE_CHECKING:
    from pykit_bench.result import BranchResult

_PAD_LEFT = 60
_PAD_TOP = 50
_PAD_RIGHT = 20
_PAD_BOTTOM = 70


def render_comparison(branches: dict[str, BranchResult], width: int = 600, height: int = 400) -> str:
    """Generate an SVG grouped bar chart comparing branches."""
    s = SvgBuilder(width, height)

    plot_w = float(width - _PAD_LEFT - _PAD_RIGHT)
    plot_h = float(height - _PAD_TOP - _PAD_BOTTOM)

    # Title
    s.text(
        width / 2,
        22,
        "Branch Comparison",
        "#333",
        16,
        'text-anchor="middle" font-weight="bold"',
    )

    # Sorted branch names
    branch_names = sorted(branches)

    # Union of metric names (sorted)
    metric_set: set[str] = set()
    for br in branches.values():
        metric_set.update(br.metrics)
    metric_names = sorted(metric_set)

    if not branch_names or not metric_names:
        return s.render()

    # Axes
    draw_axes(s, _PAD_LEFT, _PAD_TOP, plot_w, plot_h)

    # Y-axis label
    s.text(
        14,
        _PAD_TOP + plot_h / 2,
        "Value",
        "#555",
        12,
        f'text-anchor="middle" transform="rotate(-90, 14, {_PAD_TOP + plot_h / 2:.0f})"',
    )

    # Max value for scaling
    max_val = max(
        (v for br in branches.values() for v in br.metrics.values()),
        default=1.0,
    )
    if max_val <= 0:
        max_val = 1.0

    # Y-axis ticks + grid
    steps = 4
    for i in range(steps + 1):
        v = i / steps * max_val
        y = _PAD_TOP + plot_h - (i / steps) * plot_h
        s.text(_PAD_LEFT - 8, y + 4, f"{v:.2f}", "#666", 10, 'text-anchor="end"')
        s.line(float(_PAD_LEFT), y, _PAD_LEFT + plot_w, y, "#eee", 0.5)

    # Layout: groups of branches, each bar = one metric
    n_branches = len(branch_names)
    n_metrics = len(metric_names)
    group_width = plot_w / n_branches
    bar_width = group_width / (n_metrics + 1)

    for bi, b_name in enumerate(branch_names):
        br = branches[b_name]
        group_x = _PAD_LEFT + bi * group_width

        # Branch label
        s.text(
            group_x + group_width / 2,
            _PAD_TOP + plot_h + 18,
            b_name,
            "#333",
            11,
            'text-anchor="middle"',
        )

        for mi, m_name in enumerate(metric_names):
            v = br.metrics.get(m_name, 0.0)
            bar_h = (v / max_val) * plot_h
            x = group_x + mi * bar_width + bar_width * 0.15
            y = _PAD_TOP + plot_h - bar_h
            s.rect_f(x, y, bar_width * 0.7, bar_h, color_at(mi), 'opacity="0.85"')

    # Legend for metrics
    for i, m_name in enumerate(metric_names):
        lx = float(_PAD_LEFT) + 10
        ly = float(_PAD_TOP) + 10 + i * 18
        s.rect_f(lx, ly - 10, 12, 12, color_at(i))
        s.text(lx + 16, ly, m_name, "#333", 11, "")

    return s.render()
