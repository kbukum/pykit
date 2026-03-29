"""Push-based accumulator with flush triggers and FIFO eviction."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pykit_stateful.trigger import FlushTrigger, TimeTrigger


@dataclass
class AccumulatorConfig:
    """Configuration for an Accumulator."""

    max_size: int = 1000
    flush_size: int = 100
    ttl: float | None = None
    flush_interval: float | None = None


class Accumulator[V]:
    """Push-based buffer with TTL, FIFO eviction, and flush triggers."""

    def __init__(
        self,
        config: AccumulatorConfig,
        on_flush: Callable[[list[V]], Awaitable[None]],
        triggers: list[FlushTrigger[V]] | None = None,
    ) -> None:
        self._config = config
        self._on_flush = on_flush
        self._buffer: list[V] = []
        self._triggers: list[FlushTrigger[V]] = list(triggers) if triggers else []

        # Auto-add a time trigger if flush_interval is set
        if config.flush_interval is not None:
            self._triggers.append(TimeTrigger[V](config.flush_interval))

    @property
    def count(self) -> int:
        return len(self._buffer)

    async def push(self, item: V) -> None:
        """Add an item to the buffer, evicting oldest if at max_size."""
        if self._config.max_size > 0 and len(self._buffer) >= self._config.max_size:
            # FIFO eviction: drop oldest item
            self._buffer.pop(0)
        self._buffer.append(item)

        if self._should_flush():
            await self.flush()

    async def flush(self) -> None:
        """Flush the buffer and invoke the on_flush callback."""
        if not self._buffer:
            return
        items = list(self._buffer)
        self._buffer.clear()

        # Reset time triggers
        for trigger in self._triggers:
            if isinstance(trigger, TimeTrigger):
                trigger.reset()

        await self._on_flush(items)

    async def clear(self) -> None:
        """Clear the buffer without flushing."""
        self._buffer.clear()

    def _should_flush(self) -> bool:
        """Check if any trigger says we should flush."""
        return any(trigger.should_flush(self._buffer) for trigger in self._triggers)
