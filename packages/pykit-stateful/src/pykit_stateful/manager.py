"""Manager for multiplexing named accumulators."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable

from pykit_stateful.accumulator import Accumulator


class Manager[K, V]:
    """Manage multiple accumulators keyed by name or identifier."""

    def __init__(
        self,
        factory: Callable[[K], Accumulator[V]],
        cleanup_interval: float = 60.0,
    ) -> None:
        self._factory = factory
        self._cleanup_interval = cleanup_interval
        self._accumulators: dict[K, Accumulator[V]] = {}
        self._lock = asyncio.Lock()
        self._closed = False
        self._cleanup_task = asyncio.create_task(self._cleanup_loop()) if cleanup_interval > 0 else None

    async def get(self, key: K) -> Accumulator[V] | None:
        """Return the accumulator for *key*, if present."""
        async with self._lock:
            return self._accumulators.get(key)

    async def get_or_create(self, key: K) -> Accumulator[V]:
        """Return the accumulator for *key*, creating it if needed."""
        async with self._lock:
            existing = self._accumulators.get(key)
            if existing is not None:
                return existing
            accumulator = self._factory(key)
            self._accumulators[key] = accumulator
            return accumulator

    async def push(self, key: K, item: V) -> None:
        """Append *item* to the accumulator for *key*."""
        accumulator = await self.get_or_create(key)
        await accumulator.push(item)

    async def flush(self, key: K) -> None:
        """Flush the accumulator for *key* if it exists."""
        accumulator = await self.get(key)
        if accumulator is not None:
            await accumulator.flush()

    async def delete(self, key: K) -> bool:
        """Delete the accumulator for *key*."""
        async with self._lock:
            accumulator = self._accumulators.pop(key, None)
        if accumulator is None:
            return False
        await accumulator.close()
        return True

    async def keys(self) -> list[K]:
        """Return all managed keys."""
        async with self._lock:
            return list(self._accumulators.keys())

    async def cleanup(self) -> int:
        """Remove expired accumulators and return the number removed."""
        async with self._lock:
            expired = [key for key, accumulator in self._accumulators.items() if accumulator.is_expired()]
        removed = 0
        for key in expired:
            removed += int(await self.delete(key))
        return removed

    async def close(self) -> None:
        """Stop cleanup and close all managed accumulators."""
        if self._closed:
            return
        self._closed = True
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task
        async with self._lock:
            accumulators = list(self._accumulators.values())
            self._accumulators.clear()
        for accumulator in accumulators:
            await accumulator.close()

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(self._cleanup_interval)
            await self.cleanup()
