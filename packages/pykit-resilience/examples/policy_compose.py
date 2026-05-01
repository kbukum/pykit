"""Runnable policy composition example: rate -> bulkhead -> circuit -> timeout -> retry."""

from __future__ import annotations

import asyncio
import sys

from pykit_resilience import (
    BulkheadConfig,
    CircuitBreakerConfig,
    Policy,
    PolicyConfig,
    RateLimiterConfig,
    RetryConfig,
)


async def main() -> None:
    attempts = 0
    policy = Policy(
        PolicyConfig(
            rate_limiter=RateLimiterConfig(name="example", rate=10.0, burst=1),
            bulkhead=BulkheadConfig(name="example", max_concurrent=2),
            circuit_breaker=CircuitBreakerConfig(name="example", max_failures=3, timeout=1.0),
            timeout=1.0,
            retry=RetryConfig(max_attempts=3, initial_backoff=0.01, jitter=0.0),
        )
    )

    async def flaky_call() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise RuntimeError("transient failure")
        return "ok"

    result = await policy.execute(flaky_call)
    sys.stdout.write(f"{result}\n")


if __name__ == "__main__":
    asyncio.run(main())
