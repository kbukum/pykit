"""SSE event encoding."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SSEEvent:
    """A single Server-Sent Event.

    Follows the SSE wire format specification:
    https://html.spec.whatwg.org/multipage/server-sent-events.html
    """

    event: str = "message"
    data: str = ""
    id: str | None = None
    retry: int | None = None

    def encode(self) -> str:
        """Encode as SSE wire format (``event: ...\\ndata: ...\\n\\n``)."""
        lines: list[str] = []
        if self.id is not None:
            lines.append(f"id: {self.id}")
        if self.event != "message":
            lines.append(f"event: {self.event}")
        if self.retry is not None:
            lines.append(f"retry: {self.retry}")
        for line in self.data.splitlines():
            lines.append(f"data: {line}")
        if not self.data:
            lines.append("data: ")
        lines.append("")
        lines.append("")
        return "\n".join(lines)
