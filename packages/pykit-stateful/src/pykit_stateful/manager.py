"""Manager for multiplexing named accumulators."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable

from pykit_stateful.accumulator import Accumulator


class Manager[K, V]:
    """Manage multiple accumulators keyed by name or identifier.

    Prefer ``async with Manager(...)`` or call :meth:`aclose` explicitly to stop
    the lazily-started cleanup task and close managed accumulators.
    """

    def __init__(
        self,
        factory: Callable[[K], Accumulator[V]],
        cleanup_interval: float = 60.0,
    ) -> None:
        self._factory = factory
        self._cleanup_interval = cleanup_interval
        self._accumulators: dict[K, Accumulator[V]] = {}
        self._lock = asyncio.Lock()
        self._start_lock = asyncio.Lock()
        self._closed = False
        self._cleanup_task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> Manager[K, V]:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.aclose()

    async def get(self, key: K) -> Accumulator[V] | None:
        """Return the accumulator for *key*, if present."""
        async with self._lock:
            return self._accumulators.get(key)

    async def acquire(self, key: K) -> Accumulator[V]:
        """Return the accumulator for *key*, creating it if needed."""
        return await self.get_or_create(key)

    async def get_or_create(self, key: K) -> Accumulator[V]:
        """Return the accumulator for *key*, creating it if needed."""
        await self._ensure_cleanup_task()
        async with self._lock:
            if self._closed:
                raise RuntimeError("manager is closed")
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
        await accumulator.aclose()
        return True

    async def keys(self) -> list[K]:
        """Return all managed keys."""
        async with self._lock:
            return list(self._accumulators.keys())

    async def cleanup(self) -> int:
        """Remove expired accumulators and return the number removed."""
        expired: list[tuple[K, Accumulator[V]]] = []
        async with self._lock:
            for key, accumulator in self._accumulators.items():
                async with accumulator._lock:
                    if accumulator._is_expired_locked():
                        expired.append((key, accumulator))
            for key, accumulator in expired:
                if self._accumulators.get(key) is accumulator:
                    self._accumulators.pop(key)
        for _, accumulator in expired:
            await accumulator.aclose()
        return len(expired)

    async def aclose(self) -> None:
        """Stop cleanup and close all managed accumulators."""
        if self._closed:
            return
        self._closed = True
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task
            self._cleanup_task = None
        async with self._lock:
            accumulators = list(self._accumulators.values())
            self._accumulators.clear()
        for accumulator in accumulators:
            await accumulator.aclose()

    async def close(self) -> None:
        """Alias for :meth:`aclose`. Prefer ``async with`` for ownership."""
        await self.aclose()

    async def _ensure_cleanup_task(self) -> None:
        if self._cleanup_interval <= 0 or self._closed or self._cleanup_task is not None:
            return
        async with self._start_lock:
            if self._cleanup_interval > 0 and not self._closed and self._cleanup_task is None:
                self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(self._cleanup_interval)
            await self.cleanup()
