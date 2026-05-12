"""Bulkhead pattern for concurrency limiting."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from pykit_errors import AppError
from pykit_errors.codes import ErrorCode

T = TypeVar("T")


class BulkheadFullError(AppError):
    """Raised when the bulkhead has no available slots."""

    def __init__(self, name: str) -> None:
        super().__init__(ErrorCode.RATE_LIMITED, f"Bulkhead '{name}' is full")


@dataclass
class BulkheadConfig:
    """Configuration for a bulkhead."""

    name: str = "default"
    max_concurrent: int = 10
    max_wait: float = 0.0


class Bulkhead:
    """Bulkhead isolates components with a concurrency limiter.

    Uses an asyncio.Semaphore to limit the number of concurrent calls.
    """

    def __init__(self, config: BulkheadConfig | None = None) -> None:
        self._config = config or BulkheadConfig()
        self._semaphore = asyncio.Semaphore(self._config.max_concurrent)
        self._in_use = 0

    async def execute(self, fn: Callable[[], Awaitable[T]]) -> T:
        """Run fn within the concurrency limit."""
        if self._config.max_wait <= 0:
            if not self._semaphore._value:
                raise BulkheadFullError(self._config.name)
            await self._semaphore.acquire()
        else:
            try:
                await asyncio.wait_for(self._semaphore.acquire(), timeout=self._config.max_wait)
            except TimeoutError:
                raise BulkheadFullError(self._config.name) from None

        self._in_use += 1
        try:
            return await fn()
        finally:
            self._in_use -= 1
            self._semaphore.release()

    @property
    def available(self) -> int:
        """Number of available slots."""
        return self._semaphore._value

    @property
    def in_use(self) -> int:
        """Number of slots currently in use."""
        return self._in_use
