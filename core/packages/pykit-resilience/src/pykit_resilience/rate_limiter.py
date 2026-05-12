"""Rate limiter using the token bucket algorithm."""

from __future__ import annotations

import asyncio
import math
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from pykit_errors import AppError
from pykit_errors.codes import ErrorCode

T = TypeVar("T")


class RateLimitedError(AppError):
    """Raised when the rate limit is exceeded."""

    def __init__(self, name: str) -> None:
        super().__init__(ErrorCode.RATE_LIMITED, f"Rate limit exceeded for '{name}'")


@dataclass(frozen=True)
class RateLimitDecision:
    """Decision returned from a token acquisition attempt."""

    allowed: bool
    limit: int
    remaining: int
    retry_after: float
    reset_after: float


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
        if self._config.rate <= 0:
            raise ValueError("rate limiter rate must be greater than zero")
        self._tokens = float(max(self._config.burst, 1))
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()
        self._wait_lock = asyncio.Lock()

    def _refill_locked(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._last_refill = now
        if self._config.rate <= 0:
            return
        self._tokens = min(
            self._tokens + elapsed * self._config.rate,
            float(max(self._config.burst, 1)),
        )

    def take(self, *, tokens: float = 1.0) -> RateLimitDecision:
        """Try to consume *tokens* and return a structured decision."""
        limit = max(self._config.burst, 1)
        if not math.isfinite(tokens) or tokens <= 0 or tokens > limit:
            raise ValueError("tokens must be a finite positive number not greater than burst")

        with self._lock:
            self._refill_locked()
            allowed = self._tokens >= tokens
            if allowed:
                self._tokens -= tokens
                retry_after = 0.0
            elif self._config.rate > 0:
                retry_after = max((tokens - self._tokens) / self._config.rate, 0.0)
            else:
                retry_after = float("inf")

            remaining_tokens = max(self._tokens, 0.0)
            if self._config.rate > 0:
                reset_after = max((limit - remaining_tokens) / self._config.rate, 0.0)
            else:
                reset_after = 0.0

            return RateLimitDecision(
                allowed=allowed,
                limit=limit,
                remaining=max(int(remaining_tokens), 0),
                retry_after=retry_after,
                reset_after=reset_after,
            )

    def allow(self) -> bool:
        """Check if a request is allowed without blocking."""
        return self.take().allowed

    async def wait(self) -> None:
        """Block until a token is available."""
        while True:
            decision = self.take()
            if decision.allowed:
                return
            async with self._wait_lock:
                await asyncio.sleep(decision.retry_after)

    async def execute(self, fn: Callable[[], Awaitable[T]]) -> T:
        """Run fn if rate limit allows, otherwise raise RateLimitedError."""
        if not self.allow():
            raise RateLimitedError(self._config.name)
        return await fn()

    @property
    def tokens(self) -> float:
        """Current number of available tokens."""
        with self._lock:
            self._refill_locked()
            return self._tokens

    @property
    def config(self) -> RateLimiterConfig:
        """Return the active rate limiter configuration."""
        return self._config
