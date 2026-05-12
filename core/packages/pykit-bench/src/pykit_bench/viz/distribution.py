"""Score distribution histogram SVG renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pykit_bench.viz.svg_builder import SvgBuilder, color_at, draw_axes

if TYPE_CHECKING:
    from pykit_bench.curves import ScoreDistribution

_PAD_LEFT = 60
_PAD_TOP = 50
_PAD_RIGHT = 20
_PAD_BOTTOM = 50


def render_distribution(dists: list[ScoreDistribution], width: int = 600, height: int = 400) -> str:
    """Generate an SVG histogram of score distributions."""
    s = SvgBuilder(width, height)

    plot_w = float(width - _PAD_LEFT - _PAD_RIGHT)
    plot_h = float(height - _PAD_TOP - _PAD_BOTTOM)

    # Title
    s.text(
        width / 2,
        22,
        "Score Distribution",
        "#333",
        16,
        'text-anchor="middle" font-weight="bold"',
    )

    # Axes
    draw_axes(s, _PAD_LEFT, _PAD_TOP, plot_w, plot_h)

    # Axis labels
    s.text(
        _PAD_LEFT + plot_w / 2,
        height - 8,
        "Score",
        "#555",
        12,
        'text-anchor="middle"',
    )
    s.text(
        14,
        _PAD_TOP + plot_h / 2,
        "Count",
        "#555",
        12,
        f'text-anchor="middle" transform="rotate(-90, 14, {_PAD_TOP + plot_h / 2:.0f})"',
    )

    # Global max count
    max_count = (
        max(
            (c for d in dists for c in d.counts),
            default=1,
        )
        or 1
    )

    # Number of bins from the largest distribution
    num_bins = max((len(d.counts) for d in dists), default=0)
    if num_bins == 0:
        return s.render()

    group_count = len(dists)
    bin_width = plot_w / num_bins
    bar_width = bin_width / (group_count + 1)

    # X-axis tick labels
    for i in range(num_bins + 1):
        v = i / num_bins
        x = _PAD_LEFT + v * plot_w
        s.text(x, _PAD_TOP + plot_h + 18, f"{v:.1f}", "#666", 10, 'text-anchor="middle"')

    # Y-axis tick labels + grid
    steps = 4
    for i in range(steps + 1):
        v = i / steps * max_count
        y = _PAD_TOP + plot_h - (i / steps) * plot_h
        s.text(_PAD_LEFT - 8, y + 4, f"{v:.0f}", "#666", 10, 'text-anchor="end"')
        s.line(float(_PAD_LEFT), y, _PAD_LEFT + plot_w, y, "#eee", 0.5)

    # Draw bars
    for di, d in enumerate(dists):
        color = color_at(di)
        for bi, count in enumerate(d.counts):
            if count == 0:
                continue
            bar_h = (count / max_count) * plot_h
            x = _PAD_LEFT + bi * bin_width + di * bar_width + bar_width * 0.1
            y = _PAD_TOP + plot_h - bar_h
            s.rect_f(x, y, bar_width * 0.8, bar_h, color, 'opacity="0.75"')

    # Legend
    for i, d in enumerate(dists):
        lx = float(_PAD_LEFT) + 10
        ly = float(_PAD_TOP) + 10 + i * 18
        s.rect_f(lx, ly - 10, 12, 12, color_at(i))
        s.text(lx + 16, ly, d.label, "#333", 11, "")

    return s.render()
