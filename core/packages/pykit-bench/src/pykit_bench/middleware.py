"""Evaluator middleware: timing and caching wrappers."""

from __future__ import annotations

import asyncio
import hashlib
import time
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from pykit_bench.evaluator import Evaluator
    from pykit_bench.types import Prediction

L = TypeVar("L")


class TimingMiddleware[L]:
    """Wraps an evaluator to record per-sample execution timings."""

    def __init__(self, inner: Evaluator[L]) -> None:
        self._inner = inner
        self._timings: list[tuple[str, float]] = []  # (sample_id, seconds)
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        return self._inner.name

    async def is_available(self) -> bool:
        return await self._inner.is_available()

    async def evaluate(self, input: bytes) -> Prediction[L]:
        start = time.monotonic()
        result = await self._inner.evaluate(input)
        elapsed = time.monotonic() - start
        async with self._lock:
            self._timings.append((result.sample_id, elapsed))
        return result

    @property
    def timings(self) -> list[tuple[str, float]]:
        return list(self._timings)

    @property
    def average(self) -> float:
        if not self._timings:
            return 0.0
        return sum(t for _, t in self._timings) / len(self._timings)


class CachingMiddleware[L]:
    """Wraps an evaluator with input-hash-keyed caching."""

    def __init__(self, inner: Evaluator[L]) -> None:
        self._inner = inner
        self._cache: dict[str, Prediction[L]] = {}
        self._hits = 0
        self._misses = 0
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        return self._inner.name

    async def is_available(self) -> bool:
        return await self._inner.is_available()

    async def evaluate(self, input: bytes) -> Prediction[L]:
        key = hashlib.sha256(input).hexdigest()
        async with self._lock:
            if key in self._cache:
                self._hits += 1
                return self._cache[key]
        # Cache miss
        result = await self._inner.evaluate(input)
        async with self._lock:
            self._misses += 1
            self._cache[key] = result
        return result

    @property
    def hit_count(self) -> int:
        return self._hits

    @property
    def miss_count(self) -> int:
        return self._misses


def with_timing[L](evaluator: Evaluator[L]) -> TimingMiddleware[L]:
    """Wrap an evaluator with timing middleware."""
    return TimingMiddleware(evaluator)


def with_caching[L](evaluator: Evaluator[L]) -> CachingMiddleware[L]:
    """Wrap an evaluator with caching middleware."""
    return CachingMiddleware(evaluator)
