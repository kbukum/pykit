"""Example: Resilience patterns — circuit breaker, retry, rate limiter.

Demonstrates:
- CircuitBreaker protecting an unreliable service call
- Retry with exponential backoff
- RateLimiter controlling throughput
"""

from __future__ import annotations

import asyncio

from pykit_resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitOpenError,
    RateLimiter,
    RateLimiterConfig,
    RetryConfig,
    RetryExhaustedError,
    retry,
)


async def demo_circuit_breaker() -> None:
    """Show circuit breaker transitioning through states."""
    call_count = 0

    def on_state_change(name: str, old_state, new_state) -> None:
        print(f"  [{name}] state: {old_state} → {new_state}")

    cb = CircuitBreaker(
        CircuitBreakerConfig(
            name="payment-api",
            max_failures=3,
            timeout=1.0,  # seconds before half-open
            on_state_change=on_state_change,
        )
    )

    async def flaky_call() -> str:
        nonlocal call_count
        call_count += 1
        if call_count <= 3:
            raise ConnectionError(f"call #{call_count} failed")
        return "ok"

    print("=== Circuit Breaker ===")
    print(f"Initial state: {cb.state}")

    # Trigger failures until the circuit opens
    for i in range(4):
        try:
            result = await cb.execute(flaky_call)
            print(f"  Call {i + 1}: success → {result}")
        except CircuitOpenError:
            print(f"  Call {i + 1}: circuit OPEN — call rejected")
        except ConnectionError as exc:
            print(f"  Call {i + 1}: {exc}")

    print(f"Final state: {cb.state}, failures: {cb.failures}")

    # Wait for timeout, then the circuit goes half-open
    await asyncio.sleep(1.1)
    try:
        result = await cb.execute(flaky_call)
        print(f"  Recovery call: {result} (state → {cb.state})")
    except Exception as exc:
        print(f"  Recovery call failed: {exc}")


async def demo_retry() -> None:
    """Show retry with exponential backoff."""
    attempt = 0

    async def unstable_operation() -> str:
        nonlocal attempt
        attempt += 1
        if attempt < 3:
            raise TimeoutError(f"attempt {attempt} timed out")
        return f"done on attempt {attempt}"

    print("\n=== Retry with Backoff ===")
    config = RetryConfig(
        max_attempts=5,
        initial_backoff=0.05,
        backoff_factor=2.0,
        on_retry=lambda n, exc, wait: print(f"  retry #{n}, waiting {wait:.2f}s: {exc}"),
    )

    result = await retry(unstable_operation, config)
    print(f"  Result: {result}")

    # Show exhaustion
    async def always_fails() -> None:
        raise ValueError("nope")

    try:
        await retry(always_fails, RetryConfig(max_attempts=2, initial_backoff=0.01))
    except RetryExhaustedError:
        print("  RetryExhaustedError after 2 attempts (expected)")


async def demo_rate_limiter() -> None:
    """Show token-bucket rate limiter."""
    print("\n=== Rate Limiter ===")
    rl = RateLimiter(RateLimiterConfig(name="api", rate=5.0, burst=3))

    allowed = 0
    denied = 0
    for _ in range(6):
        if rl.allow():
            allowed += 1
        else:
            denied += 1

    print(f"  Sent 6 requests: {allowed} allowed, {denied} denied")
    print(f"  Remaining tokens: {rl.tokens:.1f}")


async def main() -> None:
    await demo_circuit_breaker()
    await demo_retry()
    await demo_rate_limiter()


if __name__ == "__main__":
    asyncio.run(main())
