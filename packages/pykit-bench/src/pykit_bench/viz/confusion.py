"""Confusion matrix heatmap SVG renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pykit_bench.viz.svg_builder import SvgBuilder, heat_color

if TYPE_CHECKING:
    from pykit_bench.curves import ConfusionMatrixDetail

_PAD_LEFT = 90
_PAD_TOP = 60
_PAD_RIGHT = 20
_PAD_BOTTOM = 60


def render_confusion(cm: ConfusionMatrixDetail, width: int = 600, height: int = 400) -> str:
    """Generate an SVG heatmap of a confusion matrix."""
    s = SvgBuilder(width, height)

    n = len(cm.labels)
    if n == 0:
        return s.render()

    plot_w = width - _PAD_LEFT - _PAD_RIGHT
    plot_h = height - _PAD_TOP - _PAD_BOTTOM
    cell_w = float(plot_w) / n
    cell_h = float(plot_h) / n

    # Find max value for colour scaling
    max_val = max((v for row in cm.matrix for v in row), default=1) or 1

    # Title
    s.text(
        width / 2,
        25,
        "Confusion Matrix",
        "#333",
        16,
        'text-anchor="middle" font-weight="bold"',
    )

    # Axis labels
    s.text(
        width / 2,
        height - 8,
        "Predicted",
        "#555",
        12,
        'text-anchor="middle"',
    )
    s.text(
        14,
        height / 2,
        "Actual",
        "#555",
        12,
        f'text-anchor="middle" transform="rotate(-90, 14, {height / 2:.0f})"',
    )

    # Draw cells
    for r, row in enumerate(cm.matrix):
        for c, v in enumerate(row):
            x = _PAD_LEFT + c * cell_w
            y = _PAD_TOP + r * cell_h
            intensity = v / max_val
            fill = heat_color(intensity)
            s.rect_f(x, y, cell_w, cell_h, fill, 'stroke="white" stroke-width="2"')

            text_color = "white" if intensity > 0.5 else "#333"
            s.text(
                x + cell_w / 2,
                y + cell_h / 2 + 5,
                str(v),
                text_color,
                14,
                'text-anchor="middle"',
            )

    # Column labels (predicted)
    for i, label in enumerate(cm.labels):
        x = _PAD_LEFT + i * cell_w + cell_w / 2
        s.text(x, _PAD_TOP - 8, label, "#333", 11, 'text-anchor="middle"')

    # Row labels (actual)
    for i, label in enumerate(cm.labels):
        y = _PAD_TOP + i * cell_h + cell_h / 2 + 4
        s.text(_PAD_LEFT - 8, y, label, "#333", 11, 'text-anchor="end"')

    return s.render()
