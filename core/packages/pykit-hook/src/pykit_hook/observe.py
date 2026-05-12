"""Observe-only hook Protocols."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Observer[EventT](Protocol):
    """Async observe-only hook; mutation is not part of the contract."""

    async def observe(self, event: EventT) -> None:
        """Observe an event without mutating it."""
