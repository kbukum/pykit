"""Composable resilience policies."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pykit_resilience.bulkhead import Bulkhead, BulkheadConfig
from pykit_resilience.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from pykit_resilience.rate_limiter import RateLimiter, RateLimiterConfig
from pykit_resilience.retry import RetryConfig, retry


@dataclass(frozen=True)
class PolicyConfig:
    """Configuration for a composed resilience policy."""

    retry: RetryConfig | None = None
    circuit_breaker: CircuitBreakerConfig | None = None
    bulkhead: BulkheadConfig | None = None
    rate_limiter: RateLimiterConfig | None = None
    timeout: float | None = None


class Policy:
    """Compose multiple resilience primitives into one execution policy."""

    def __init__(self, config: PolicyConfig) -> None:
        self._config = config
        self._rate_limiter = RateLimiter(config.rate_limiter) if config.rate_limiter is not None else None
        self._bulkhead = Bulkhead(config.bulkhead) if config.bulkhead is not None else None
        self._circuit_breaker = (
            CircuitBreaker(config.circuit_breaker) if config.circuit_breaker is not None else None
        )

    async def execute[T](self, fn: Callable[[], Awaitable[T]]) -> T:
        """Execute *fn* through the configured resilience stack."""

        async def execute_retry() -> T:
            if self._config.retry is None:
                return await fn()
            return await retry(fn, self._config.retry)

        async def execute_timeout() -> T:
            if self._config.timeout is None:
                return await execute_retry()
            async with asyncio.timeout(self._config.timeout):
                return await execute_retry()

        async def execute_circuit_breaker() -> T:
            if self._circuit_breaker is None:
                return await execute_timeout()
            return await self._circuit_breaker.execute(execute_timeout)

        async def execute_bulkhead() -> T:
            if self._bulkhead is None:
                return await execute_circuit_breaker()
            return await self._bulkhead.execute(execute_circuit_breaker)

        if self._rate_limiter is None:
            return await execute_bulkhead()
        return await self._rate_limiter.execute(execute_bulkhead)
