"""Comprehensive tests for pykit-resilience."""

from __future__ import annotations

import asyncio
import time

import pytest

from pykit_errors import AppError
from pykit_resilience import (
    Bulkhead,
    BulkheadConfig,
    BulkheadFullError,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitOpenError,
    RateLimitedError,
    RateLimiter,
    RateLimiterConfig,
    RetryConfig,
    RetryExhaustedError,
    State,
    retry,
)

# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------


class TestCircuitBreakerState:
    def test_initial_state_is_closed(self) -> None:
        cb = CircuitBreaker()
        assert cb.state == State.CLOSED
        assert cb.failures == 0

    @pytest.mark.asyncio
    async def test_success_keeps_closed(self) -> None:
        cb = CircuitBreaker()

        async def ok() -> int:
            return 42

        result = await cb.execute(ok)
        assert result == 42
        assert cb.state == State.CLOSED
        assert cb.failures == 0

    @pytest.mark.asyncio
    async def test_failures_open_circuit(self) -> None:
        cfg = CircuitBreakerConfig(name="test", max_failures=3)
        cb = CircuitBreaker(cfg)

        async def fail() -> None:
            raise RuntimeError("boom")

        for _ in range(3):
            with pytest.raises(RuntimeError):
                await cb.execute(fail)

        assert cb.state == State.OPEN
        assert cb.failures == 3

    @pytest.mark.asyncio
    async def test_open_circuit_rejects(self) -> None:
        cfg = CircuitBreakerConfig(name="test", max_failures=1)
        cb = CircuitBreaker(cfg)

        async def fail() -> None:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await cb.execute(fail)

        assert cb.state == State.OPEN

        with pytest.raises(CircuitOpenError) as exc_info:
            await cb.execute(fail)

        assert isinstance(exc_info.value, AppError)
        assert "test" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self) -> None:
        cfg = CircuitBreakerConfig(name="test", max_failures=1, timeout=0.05)
        cb = CircuitBreaker(cfg)

        async def fail() -> None:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await cb.execute(fail)

        assert cb.state == State.OPEN
        await asyncio.sleep(0.06)
        assert cb.state == State.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_success_closes(self) -> None:
        cfg = CircuitBreakerConfig(name="test", max_failures=1, timeout=0.05, half_open_max_calls=1)
        cb = CircuitBreaker(cfg)

        async def fail() -> None:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await cb.execute(fail)

        await asyncio.sleep(0.06)
        assert cb.state == State.HALF_OPEN

        result = await cb.execute(lambda: asyncio.sleep(0, result=99))
        assert result == 99
        assert cb.state == State.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens(self) -> None:
        cfg = CircuitBreakerConfig(name="test", max_failures=1, timeout=0.05)
        cb = CircuitBreaker(cfg)

        async def fail() -> None:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await cb.execute(fail)

        await asyncio.sleep(0.06)
        assert cb.state == State.HALF_OPEN

        with pytest.raises(RuntimeError):
            await cb.execute(fail)

        assert cb.state == State.OPEN

    @pytest.mark.asyncio
    async def test_half_open_limits_calls(self) -> None:
        cfg = CircuitBreakerConfig(name="test", max_failures=1, timeout=0.05, half_open_max_calls=1)
        cb = CircuitBreaker(cfg)

        async def fail() -> None:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await cb.execute(fail)

        await asyncio.sleep(0.06)

        # First call to half-open: allowed (will block the slot)
        # We use a slow task to keep the slot occupied
        started = asyncio.Event()
        proceed = asyncio.Event()

        async def slow() -> int:
            started.set()
            await proceed.wait()
            return 1

        task = asyncio.create_task(cb.execute(slow))
        await started.wait()

        # Second call should be rejected while first holds the slot
        with pytest.raises(CircuitOpenError):
            await cb.execute(lambda: asyncio.sleep(0, result=2))

        proceed.set()
        assert await task == 1

    def test_reset(self) -> None:
        cfg = CircuitBreakerConfig(name="test", max_failures=1)
        cb = CircuitBreaker(cfg)
        # Manually force state
        cb._state = State.OPEN
        cb._failures = 5
        cb.reset()
        assert cb.state == State.CLOSED
        assert cb.failures == 0

    def test_on_state_change_callback(self) -> None:
        transitions: list[tuple[str, State, State]] = []
        cfg = CircuitBreakerConfig(
            name="cb",
            max_failures=1,
            on_state_change=lambda n, f, t: transitions.append((n, f, t)),
        )
        cb = CircuitBreaker(cfg)
        # Force open
        cb._failures = 1
        cb._last_failure_time = time.monotonic()
        cb._to_state(State.OPEN)
        assert transitions == [("cb", State.CLOSED, State.OPEN)]

    @pytest.mark.asyncio
    async def test_half_open_max_calls_exceeded_returns_false(self) -> None:
        """Cover circuit_breaker.py line 110: _allow_request returns False
        when half_open_calls >= half_open_max_calls and state is HALF_OPEN,
        falling through to the final return False."""
        cfg = CircuitBreakerConfig(name="test", max_failures=1, timeout=0.01, half_open_max_calls=1)
        cb = CircuitBreaker(cfg)

        async def fail() -> None:
            raise RuntimeError("boom")

        # Trip the breaker
        with pytest.raises(RuntimeError):
            await cb.execute(fail)
        assert cb.state == State.OPEN

        await asyncio.sleep(0.02)
        assert cb.state == State.HALF_OPEN

        # Consume the single allowed half-open call
        cb._half_open_calls = cb._config.half_open_max_calls
        # Now the next call should be rejected (hits line 109 → False, then line 110)
        with pytest.raises(CircuitOpenError):
            await cb.execute(lambda: asyncio.sleep(0, result=1))

    def test_to_state_noop_when_already_in_state(self) -> None:
        """Cover circuit_breaker.py line 141: _to_state is a no-op when from==to."""
        transitions: list[tuple[str, State, State]] = []
        cfg = CircuitBreakerConfig(
            name="noop",
            on_state_change=lambda n, f, t: transitions.append((n, f, t)),
        )
        cb = CircuitBreaker(cfg)
        assert cb._state == State.CLOSED
        cb._to_state(State.CLOSED)  # no-op
        assert transitions == []  # callback should NOT fire


# ---------------------------------------------------------------------------
# Retry
# ---------------------------------------------------------------------------


class TestRetry:
    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self) -> None:
        calls = 0

        async def fn() -> str:
            nonlocal calls
            calls += 1
            return "ok"

        result = await retry(fn)
        assert result == "ok"
        assert calls == 1

    @pytest.mark.asyncio
    async def test_retries_then_succeeds(self) -> None:
        calls = 0

        async def fn() -> str:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise RuntimeError("not yet")
            return "ok"

        result = await retry(fn, RetryConfig(max_attempts=3, initial_backoff=0.01))
        assert result == "ok"
        assert calls == 3

    @pytest.mark.asyncio
    async def test_exhausted_raises(self) -> None:
        async def fn() -> None:
            raise RuntimeError("always fails")

        with pytest.raises(RetryExhaustedError) as exc_info:
            await retry(fn, RetryConfig(max_attempts=2, initial_backoff=0.01))

        assert exc_info.value.attempts == 2
        assert isinstance(exc_info.value.last_error, RuntimeError)
        assert isinstance(exc_info.value, AppError)

    @pytest.mark.asyncio
    async def test_retry_if_skips_non_retriable(self) -> None:
        class PermanentError(Exception):
            pass

        calls = 0

        async def fn() -> None:
            nonlocal calls
            calls += 1
            raise PermanentError("stop")

        with pytest.raises(PermanentError):
            await retry(
                fn,
                RetryConfig(
                    max_attempts=5,
                    initial_backoff=0.01,
                    retry_if=lambda e: not isinstance(e, PermanentError),
                ),
            )

        assert calls == 1

    @pytest.mark.asyncio
    async def test_on_retry_callback(self) -> None:
        retries: list[tuple[int, str]] = []
        calls = 0

        async def fn() -> str:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise RuntimeError(f"fail-{calls}")
            return "done"

        result = await retry(
            fn,
            RetryConfig(
                max_attempts=3,
                initial_backoff=0.01,
                on_retry=lambda a, e, b: retries.append((a, str(e))),
            ),
        )
        assert result == "done"
        assert len(retries) == 2
        assert retries[0][0] == 1
        assert retries[1][0] == 2

    @pytest.mark.asyncio
    async def test_backoff_timing(self) -> None:
        """Verify backoff delays are applied."""
        calls = 0

        async def fn() -> str:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise RuntimeError("fail")
            return "ok"

        start = time.monotonic()
        await retry(
            fn,
            RetryConfig(
                max_attempts=3,
                initial_backoff=0.05,
                backoff_factor=1.0,
                jitter=0.0,
            ),
        )
        elapsed = time.monotonic() - start
        assert elapsed >= 0.09  # ~2 sleeps of 0.05s each

    @pytest.mark.asyncio
    async def test_default_config(self) -> None:
        cfg = RetryConfig()
        assert cfg.max_attempts == 3
        assert cfg.initial_backoff == 0.1
        assert cfg.max_backoff == 10.0
        assert cfg.backoff_factor == 2.0
        assert cfg.jitter == 0.1


# ---------------------------------------------------------------------------
# Bulkhead
# ---------------------------------------------------------------------------


class TestBulkhead:
    @pytest.mark.asyncio
    async def test_basic_execution(self) -> None:
        bh = Bulkhead(BulkheadConfig(name="test", max_concurrent=2))
        result = await bh.execute(lambda: asyncio.sleep(0, result=42))
        assert result == 42
        assert bh.available == 2
        assert bh.in_use == 0

    @pytest.mark.asyncio
    async def test_rejects_when_full(self) -> None:
        bh = Bulkhead(BulkheadConfig(name="test", max_concurrent=1, max_wait=0))

        started = asyncio.Event()
        proceed = asyncio.Event()

        async def slow() -> int:
            started.set()
            await proceed.wait()
            return 1

        task = asyncio.create_task(bh.execute(slow))
        await started.wait()

        assert bh.in_use == 1
        assert bh.available == 0

        with pytest.raises(BulkheadFullError) as exc_info:
            await bh.execute(lambda: asyncio.sleep(0, result=2))

        assert isinstance(exc_info.value, AppError)
        assert "test" in str(exc_info.value)

        proceed.set()
        assert await task == 1

    @pytest.mark.asyncio
    async def test_releases_on_error(self) -> None:
        bh = Bulkhead(BulkheadConfig(name="test", max_concurrent=1))

        async def fail() -> None:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await bh.execute(fail)

        assert bh.available == 1
        assert bh.in_use == 0

    @pytest.mark.asyncio
    async def test_concurrency_limit(self) -> None:
        bh = Bulkhead(BulkheadConfig(name="test", max_concurrent=3, max_wait=5.0))
        max_concurrent_seen = 0
        lock = asyncio.Lock()

        async def tracked() -> None:
            nonlocal max_concurrent_seen
            async with lock:
                if bh.in_use > max_concurrent_seen:
                    max_concurrent_seen = bh.in_use
            await asyncio.sleep(0.05)

        tasks = [asyncio.create_task(bh.execute(tracked)) for _ in range(6)]
        await asyncio.gather(*tasks)

        assert max_concurrent_seen <= 3

    @pytest.mark.asyncio
    async def test_max_wait_allows_queuing(self) -> None:
        bh = Bulkhead(BulkheadConfig(name="test", max_concurrent=1, max_wait=1.0))

        async def fast() -> int:
            await asyncio.sleep(0.02)
            return 1

        results = await asyncio.gather(
            bh.execute(fast),
            bh.execute(fast),
        )
        assert results == [1, 1]

    @pytest.mark.asyncio
    async def test_max_wait_timeout(self) -> None:
        bh = Bulkhead(BulkheadConfig(name="test", max_concurrent=1, max_wait=0.02))

        started = asyncio.Event()

        async def slow() -> int:
            started.set()
            await asyncio.sleep(1.0)
            return 1

        task = asyncio.create_task(bh.execute(slow))
        await started.wait()

        with pytest.raises(BulkheadFullError):
            await bh.execute(lambda: asyncio.sleep(0, result=2))

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------


class TestRateLimiter:
    def test_allow_within_burst(self) -> None:
        rl = RateLimiter(RateLimiterConfig(name="test", rate=10.0, burst=5))
        for _ in range(5):
            assert rl.allow() is True
        assert rl.allow() is False

    def test_tokens_refill(self) -> None:
        rl = RateLimiter(RateLimiterConfig(name="test", rate=100.0, burst=10))
        for _ in range(10):
            rl.allow()
        assert rl.tokens < 1.0
        time.sleep(0.1)
        assert rl.tokens >= 9.0

    @pytest.mark.asyncio
    async def test_execute_allowed(self) -> None:
        rl = RateLimiter(RateLimiterConfig(name="test", rate=10.0, burst=5))
        result = await rl.execute(lambda: asyncio.sleep(0, result=42))
        assert result == 42

    @pytest.mark.asyncio
    async def test_execute_rejected(self) -> None:
        rl = RateLimiter(RateLimiterConfig(name="test", rate=10.0, burst=1))
        await rl.execute(lambda: asyncio.sleep(0, result=1))

        with pytest.raises(RateLimitedError) as exc_info:
            await rl.execute(lambda: asyncio.sleep(0, result=2))

        assert isinstance(exc_info.value, AppError)
        assert "test" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_wait_blocks_until_available(self) -> None:
        rl = RateLimiter(RateLimiterConfig(name="test", rate=100.0, burst=1))
        assert rl.allow() is True

        start = time.monotonic()
        await rl.wait()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.005  # should wait ~0.01s for 1 token at 100/s

    def test_default_config(self) -> None:
        rl = RateLimiter()
        assert rl.tokens == 20.0

    def test_tokens_property(self) -> None:
        rl = RateLimiter(RateLimiterConfig(name="test", rate=10.0, burst=10))
        assert rl.tokens == 10.0
        rl.allow()
        assert rl.tokens < 10.0

    @pytest.mark.asyncio
    async def test_high_rate_burst(self) -> None:
        rl = RateLimiter(RateLimiterConfig(name="test", rate=1.0, burst=100))
        allowed = sum(1 for _ in range(100) if rl.allow())
        assert allowed == 100
        assert rl.allow() is False
