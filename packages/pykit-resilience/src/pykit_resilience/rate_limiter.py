"""Rate limiter using the token bucket algorithm."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

import grpc

from pykit_errors import AppError

T = TypeVar("T")


class RateLimitedError(AppError):
    """Raised when the rate limit is exceeded."""

    grpc_status = grpc.StatusCode.RESOURCE_EXHAUSTED

    def __init__(self, name: str) -> None:
        super().__init__(f"Rate limit exceeded for '{name}'")


@dataclass
class RateLimiterConfig:
    """Configuration for a rate limiter."""

    name: str = "default"
    rate: float = 10.0
    burst: int = 20


class RateLimiter:
    """Token bucket rate limiter.

    Controls the rate of requests by maintaining a bucket of tokens that
    refill at a fixed rate. Each request consumes one token.
    """

    def __init__(self, config: RateLimiterConfig | None = None) -> None:
        self._config = config or RateLimiterConfig()
        self._tokens = float(self._config.burst)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._last_refill = now
        self._tokens = min(
            self._tokens + elapsed * self._config.rate,
            float(self._config.burst),
        )

    def allow(self) -> bool:
        """Check if a request is allowed without blocking.

        Returns True if a token was consumed, False if rate limited.
        """
        self._refill()
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False

    async def wait(self) -> None:
        """Block until a token is available."""
        async with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return
            needed = 1.0 - self._tokens
            wait_seconds = needed / self._config.rate
            self._tokens -= 1.0
        await asyncio.sleep(wait_seconds)

    async def execute(self, fn: Callable[[], Awaitable[T]]) -> T:
        """Run fn if rate limit allows, otherwise raise RateLimitedError."""
        if not self.allow():
            raise RateLimitedError(self._config.name)
        return await fn()

    @property
    def tokens(self) -> float:
        """Current number of available tokens."""
        self._refill()
        return self._tokens
