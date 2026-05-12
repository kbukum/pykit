"""ROC curve SVG renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pykit_bench.viz.svg_builder import Point, SvgBuilder, draw_axes

if TYPE_CHECKING:
    from pykit_bench.curves import RocCurve

_PAD_LEFT = 60
_PAD_TOP = 40
_PAD_RIGHT = 20
_PAD_BOTTOM = 50


def render_roc(roc: RocCurve, width: int = 600, height: int = 400) -> str:
    """Generate an SVG plot of a Receiver Operating Characteristic curve."""
    s = SvgBuilder(width, height)

    plot_w = float(width - _PAD_LEFT - _PAD_RIGHT)
    plot_h = float(height - _PAD_TOP - _PAD_BOTTOM)

    # Title
    s.text(
        width / 2,
        22,
        "ROC Curve",
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
        "False Positive Rate",
        "#555",
        12,
        'text-anchor="middle"',
    )
    s.text(
        14,
        _PAD_TOP + plot_h / 2,
        "True Positive Rate",
        "#555",
        12,
        f'text-anchor="middle" transform="rotate(-90, 14, {_PAD_TOP + plot_h / 2:.0f})"',
    )

    # Tick labels + grid
    for i in range(5):
        v = i / 4.0
        x = _PAD_LEFT + v * plot_w
        y = _PAD_TOP + plot_h
        s.text(x, y + 18, f"{v:.2f}", "#666", 10, 'text-anchor="middle"')
        s.line(x, float(_PAD_TOP), x, y, "#eee", 0.5)

    for i in range(5):
        v = i / 4.0
        x = float(_PAD_LEFT)
        y = _PAD_TOP + plot_h - v * plot_h
        s.text(x - 8, y + 4, f"{v:.2f}", "#666", 10, 'text-anchor="end"')
        s.line(float(_PAD_LEFT), y, _PAD_LEFT + plot_w, y, "#eee", 0.5)

    # Diagonal reference (dashed)
    s.line(
        float(_PAD_LEFT),
        _PAD_TOP + plot_h,
        _PAD_LEFT + plot_w,
        float(_PAD_TOP),
        "#999",
        1,
        'stroke-dasharray="6,4"',
    )

    # ROC curve polyline
    if roc.fpr and len(roc.fpr) == len(roc.tpr):
        pts = [
            Point(
                x=_PAD_LEFT + fpr * plot_w,
                y=_PAD_TOP + plot_h - tpr * plot_h,
            )
            for fpr, tpr in zip(roc.fpr, roc.tpr, strict=True)
        ]
        s.polyline(pts, "#4285F4", 2, "none")

    # AUC annotation
    s.text(
        _PAD_LEFT + plot_w - 10,
        _PAD_TOP + 20,
        f"AUC = {roc.auc:.4f}",
        "#4285F4",
        13,
        'text-anchor="end" font-weight="bold"',
    )

    return s.render()
