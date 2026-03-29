"""Low-level SVG element builder.

Constructs valid standalone SVG documents using only stdlib string
operations — no external dependencies required.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape as _html_escape


@dataclass
class Point:
    """A 2-D coordinate."""

    x: float
    y: float


PALETTE = (
    "#4285F4",  # blue
    "#EA4335",  # red
    "#34A853",  # green
    "#FBBC05",  # yellow
    "#9C27B0",  # purple
    "#FF6D00",  # orange
    "#00BCD4",  # cyan
    "#795548",  # brown
)


def color_at(i: int) -> str:
    """Return the *i*-th palette colour (wraps around)."""
    return PALETTE[i % len(PALETTE)]


def heat_color(t: float) -> str:
    """Interpolate light blue (#E3F2FD) at 0.0 → dark blue (#1565C0) at 1.0."""
    t = max(0.0, min(1.0, t))
    r = int(227 - t * 114)  # 227 → 113
    g = int(242 - t * 141)  # 242 → 101
    b = int(253 - t * 61)  # 253 → 192
    return f"#{r:02X}{g:02X}{b:02X}"


def clamp01(v: float) -> float:
    """Clamp *v* to the [0, 1] range."""
    return max(0.0, min(1.0, v))


def xml_escape(s: str) -> str:
    """Escape XML special characters."""
    return _html_escape(s, quote=True)


class SvgBuilder:
    """Lightweight builder for constructing SVG documents."""

    def __init__(self, width: int, height: int) -> None:
        self._w = width
        self._h = height
        self._elements: list[str] = []

    # ------------------------------------------------------------------
    # Primitive elements
    # ------------------------------------------------------------------

    def rect(self, x: int, y: int, w: int, h: int, fill: str, attrs: str = "") -> None:
        """Append a ``<rect>`` with integer coordinates."""
        self._elements.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" {attrs}/>'
        )

    def rect_f(self, x: float, y: float, w: float, h: float, fill: str, attrs: str = "") -> None:
        """Append a ``<rect>`` with float coordinates (2 d.p.)."""
        self._elements.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" '
            f'height="{h:.2f}" fill="{fill}" {attrs}/>'
        )

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        stroke: str,
        stroke_width: float,
        attrs: str = "",
    ) -> None:
        """Append a ``<line>`` element."""
        self._elements.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            f'stroke="{stroke}" stroke-width="{stroke_width:.1f}" {attrs}/>'
        )

    def text(
        self,
        x: float,
        y: float,
        content: str,
        fill: str,
        font_size: int,
        attrs: str = "",
    ) -> None:
        """Append a ``<text>`` element."""
        self._elements.append(
            f'<text x="{x:.2f}" y="{y:.2f}" fill="{fill}" font-size="{font_size}" '
            f'font-family="sans-serif" {attrs}>{xml_escape(content)}</text>'
        )

    def circle(self, cx: float, cy: float, r: float, fill: str, attrs: str = "") -> None:
        """Append a ``<circle>`` element."""
        self._elements.append(
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{fill}" {attrs}/>'
        )

    def polyline(
        self,
        points: list[Point],
        stroke: str,
        stroke_width: float,
        fill: str,
        attrs: str = "",
    ) -> None:
        """Append a ``<polyline>`` element."""
        if not points:
            return
        pts = " ".join(f"{p.x:.2f},{p.y:.2f}" for p in points)
        self._elements.append(
            f'<polyline points="{pts}" stroke="{stroke}" '
            f'stroke-width="{stroke_width:.1f}" fill="{fill}" {attrs}/>'
        )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def render(self) -> str:
        """Return the complete SVG document as a string."""
        parts: list[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self._w}" '
            f'height="{self._h}" viewBox="0 0 {self._w} {self._h}">',
            f'<rect width="{self._w}" height="{self._h}" fill="white"/>',
            *self._elements,
            "</svg>",
        ]
        return "\n".join(parts)


def draw_axes(svg: SvgBuilder, pad_left: int, pad_top: int, plot_w: float, plot_h: float) -> None:
    """Draw Y-axis and X-axis lines for a standard plot area."""
    x0 = float(pad_left)
    y0 = float(pad_top)
    # Y axis
    svg.line(x0, y0, x0, y0 + plot_h, "#333", 1.5)
    # X axis
    svg.line(x0, y0 + plot_h, x0 + plot_w, y0 + plot_h, "#333", 1.5)
