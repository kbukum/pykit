# pykit-resilience

Resilience patterns for async Python: circuit breaker, retry with backoff, bulkhead, rate limiter, and degradation management.

## Installation

```bash
pip install pykit-resilience
# or
uv add pykit-resilience
```

## Quick Start

```python
from pykit_resilience import (
    CircuitBreaker, CircuitBreakerConfig,
    retry, RetryConfig,
    Bulkhead, BulkheadConfig,
    RateLimiter, RateLimiterConfig,
    DegradationManager,
)

# Circuit Breaker — opens after 5 failures, resets after 30s
cb = CircuitBreaker(CircuitBreakerConfig(max_failures=5, timeout=30.0))
result = await cb.execute(lambda: call_external_service())

# Retry with exponential backoff and jitter
result = await retry(
    lambda: fetch_data(),
    RetryConfig(max_attempts=3, initial_backoff=0.1, backoff_factor=2.0),
)

# Bulkhead — limit to 10 concurrent calls
bh = Bulkhead(BulkheadConfig(max_concurrent=10, max_wait=5.0))
result = await bh.execute(lambda: process_request())

# Rate Limiter — token bucket at 100 req/s with burst of 50
rl = RateLimiter(RateLimiterConfig(rate=100.0, burst=50))
result = await rl.execute(lambda: handle_request())
```

### Degradation Manager

```python
dm = DegradationManager()
dm.update_service("db", ServiceHealth.HEALTHY)
dm.set_feature("experimental-ui", dm.is_healthy())

# Wire circuit breaker state changes to degradation manager
cb = CircuitBreaker(CircuitBreakerConfig(
    on_state_change=dm.on_circuit_breaker_state_change("db-service"),
))
```

## Key Components

- **CircuitBreaker** — Classic circuit breaker (CLOSED → OPEN → HALF_OPEN) with configurable failure threshold and recovery timeout
- **retry()** — Async retry with exponential backoff, jitter, configurable retry predicate, and callback
- **Bulkhead** — Semaphore-based concurrency limiter with optional wait timeout
- **RateLimiter** — Token bucket rate limiter with `allow()`, `wait()`, and `execute()` methods
- **DegradationManager** — Thread-safe service health tracker with feature flags and circuit breaker integration
- **CircuitOpenError / RetryExhaustedError** — Use `ErrorCode.SERVICE_UNAVAILABLE`
- **BulkheadFullError / RateLimitedError** — Use `ErrorCode.RATE_LIMITED`

## Dependencies

- `pykit-errors`

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
