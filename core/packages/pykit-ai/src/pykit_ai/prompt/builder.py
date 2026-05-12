"""Prompt builder utilities."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Builder:
    """Incrementally build a prompt from titled sections."""

    _sections: list[tuple[str, str]] = field(default_factory=list)

    def add(self, title: str, body: str) -> Builder:
        """Add a section and return this builder."""
        self._sections.append((title, body))
        return self

    def render(self) -> str:
        """Render all sections separated by blank lines."""
        return "\n\n".join(f"## {title}\n{body}" if title else body for title, body in self._sections)
