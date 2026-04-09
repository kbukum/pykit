"""Execution context for tool calls."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Context:
    """Execution context passed to tool calls.

    Carries request metadata, cancellation signaling, and arbitrary
    key-value data for cross-cutting concerns (e.g. tracing, auth).
    """

    request_id: str = ""
    tool_use_id: str = ""
    max_result_size: int = 0
    _metadata: dict[str, Any] = field(default_factory=dict)
    _cancel_event: asyncio.Event = field(default_factory=asyncio.Event)

    def set(self, key: str, value: Any) -> None:
        """Store a metadata value."""
        self._metadata[key] = value

    def get(self, key: str) -> Any | None:
        """Retrieve a metadata value, or None."""
        return self._metadata.get(key)

    @property
    def metadata(self) -> dict[str, Any]:
        """Return a shallow copy of all metadata."""
        return dict(self._metadata)

    def cancel(self) -> None:
        """Signal cancellation."""
        self._cancel_event.set()

    @property
    def cancelled(self) -> bool:
        """Return True if cancellation has been signaled."""
        return self._cancel_event.is_set()
