"""Push-based accumulator with flush triggers and TTL cleanup."""

from __future__ import annotations

import asyncio
import contextlib
import time
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
    """Push-based buffer with TTL, FIFO eviction, and flush triggers.

    Prefer ``async with Accumulator(...)`` or call :meth:`aclose` explicitly to
    stop the lazily-started TTL cleanup task.
    """

    def __init__(
        self,
        config: AccumulatorConfig,
        on_flush: Callable[[list[V]], Awaitable[None]],
        triggers: list[FlushTrigger[V]] | None = None,
    ) -> None:
        self._config = config
        self._on_flush = on_flush
        self._buffer: list[V] = []
        self._lock = asyncio.Lock()
        self._start_lock = asyncio.Lock()
        self._closed = False
        self._last_activity = time.monotonic()
        self._triggers: list[FlushTrigger[V]] = list(triggers) if triggers else []

        if config.flush_interval is not None:
            self._triggers.append(TimeTrigger[V](config.flush_interval))

        self._ttl_task: asyncio.Task[None] | None = None

    @property
    def count(self) -> int:
        return len(self._buffer)

    async def __aenter__(self) -> Accumulator[V]:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.aclose()

    async def push(self, item: V) -> None:
        """Add an item to the buffer, evicting oldest if at max_size."""
        await self._ensure_ttl_task()
        items_to_flush: list[V] | None = None
        async with self._lock:
            if self._closed:
                raise RuntimeError("accumulator is closed")
            if self._config.max_size > 0 and len(self._buffer) >= self._config.max_size:
                self._buffer.pop(0)
            self._buffer.append(item)
            self._touch_locked()
            if self._should_flush_locked():
                items_to_flush = self._prepare_flush_locked()
        if items_to_flush is not None:
            await self._on_flush(items_to_flush)

    async def flush(self) -> None:
        """Flush the buffer and invoke the on_flush callback."""
        async with self._lock:
            items_to_flush = self._prepare_flush_locked()
        if items_to_flush is not None:
            await self._on_flush(items_to_flush)

    async def clear(self) -> None:
        """Clear the buffer without flushing."""
        async with self._lock:
            self._clear_locked(touch=True)

    def is_expired(self) -> bool:
        """Return a non-authoritative expiry snapshot.

        Cleanup paths re-check expiry while holding ``_lock`` before mutating
        the buffer, so this snapshot is informational only.
        """
        if self._config.ttl is None:
            return False
        return (time.monotonic() - self._last_activity) >= self._config.ttl

    async def aclose(self) -> None:
        """Stop background cleanup for this accumulator."""
        if self._closed:
            return
        self._closed = True
        if self._ttl_task is not None:
            self._ttl_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._ttl_task
            self._ttl_task = None

    async def close(self) -> None:
        """Alias for :meth:`aclose`. Prefer ``async with`` for ownership."""
        await self.aclose()

    async def _ensure_ttl_task(self) -> None:
        if self._config.ttl is None or self._closed or self._ttl_task is not None:
            return
        async with self._start_lock:
            if self._config.ttl is not None and not self._closed and self._ttl_task is None:
                self._ttl_task = asyncio.create_task(self._ttl_cleanup_loop())

    def _touch_locked(self) -> None:
        self._last_activity = time.monotonic()

    def _is_expired_locked(self) -> bool:
        if self._config.ttl is None:
            return False
        return (time.monotonic() - self._last_activity) >= self._config.ttl

    def _clear_locked(self, *, touch: bool) -> None:
        self._buffer.clear()
        if touch:
            self._touch_locked()

    def _prepare_flush_locked(self) -> list[V] | None:
        if not self._buffer:
            return None
        items = list(self._buffer)
        self._buffer.clear()
        self._touch_locked()
        for trigger in self._triggers:
            if isinstance(trigger, TimeTrigger):
                trigger.reset()
        return items

    def _should_flush_locked(self) -> bool:
        return any(trigger.should_flush(self._buffer) for trigger in self._triggers)

    async def _ttl_cleanup_loop(self) -> None:
        assert self._config.ttl is not None
        interval = max(self._config.ttl / 4, 0.01)
        while True:
            await asyncio.sleep(interval)
            async with self._lock:
                if self._is_expired_locked():
                    self._clear_locked(touch=False)
