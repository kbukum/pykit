"""Flush trigger protocols and built-in implementations."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol, runtime_checkable


@runtime_checkable
class FlushTrigger[V](Protocol):
    """Determines whether an accumulator should flush."""

    def should_flush(self, items: list[V]) -> bool: ...


class SizeTrigger[V]:
    """Flush when item count reaches threshold."""

    def __init__(self, threshold: int) -> None:
        self._threshold = threshold

    def should_flush(self, items: list[V]) -> bool:
        return len(items) >= self._threshold


class ByteSizeTrigger:
    """Flush when total byte size of items reaches threshold.

    Requires a measurer function that returns byte size for an item.
    """

    def __init__(self, threshold: int, measurer: Callable[[bytes], int] | None = None) -> None:
        self._threshold = threshold
        self._measurer = measurer or len

    def should_flush(self, items: list[bytes]) -> bool:
        total = sum(self._measurer(item) for item in items)
        return total >= self._threshold


class TimeTrigger[V]:
    """Flush after a time interval (seconds) since last flush or creation."""

    def __init__(self, interval: float) -> None:
        self._interval = interval
        self._last_flush: float = time.monotonic()

    def should_flush(self, items: list[V]) -> bool:
        return (time.monotonic() - self._last_flush) >= self._interval

    def reset(self) -> None:
        self._last_flush = time.monotonic()
