"""Extended TDD tests for pykit-resilience — filling gaps in the existing suite."""

from __future__ import annotations

import asyncio
import threading
import time

import pytest

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
from pykit_resilience.degradation import (
    DegradationManager,
    ServiceHealth,
)

# ---------------------------------------------------------------------------
# 1. Circuit Breaker Edge Cases
# ---------------------------------------------------------------------------


class TestCircuitBreakerEdgeCases:
    async def test_half_open_concurrent_probes_exactly_max(self) -> None:
        """Exactly half_open_max_calls probes should be allowed in half-open."""
        cfg = CircuitBreakerConfig(name="ho-max", max_failures=1, timeout=0.01, half_open_max_calls=3)
        cb = CircuitBreaker(cfg)

        async def fail() -> None:
            raise RuntimeError("trip")

        with pytest.raises(RuntimeError):
            await cb.execute(fail)
        await asyncio.sleep(0.02)
        assert cb.state == State.HALF_OPEN

        started = []
        proceed = asyncio.Event()

        async def slow(idx: int) -> int:
            started.append(idx)
            await proceed.wait()
            return idx

        tasks = [asyncio.create_task(cb.execute(lambda i=i: slow(i))) for i in range(3)]
        await asyncio.sleep(0.05)

        # 4th call should be rejected while 3 probes hold slots
        with pytest.raises(CircuitOpenError):
            await cb.execute(lambda: asyncio.sleep(0, result=99))

        proceed.set()
        results = await asyncio.gather(*tasks)
        assert sorted(results) == [0, 1, 2]
        assert cb.state == State.CLOSED

    async def test_half_open_single_failure_reopens(self) -> None:
        """A single failure during half-open should reopen the circuit."""
        cfg = CircuitBreakerConfig(name="ho-fail", max_failures=1, timeout=0.01, half_open_max_calls=3)
        cb = CircuitBreaker(cfg)

        async def fail() -> None:
            raise RuntimeError("trip")

        with pytest.raises(RuntimeError):
            await cb.execute(fail)
        await asyncio.sleep(0.02)
        assert cb.state == State.HALF_OPEN

        with pytest.raises(RuntimeError):
            await cb.execute(fail)
        assert cb.state == State.OPEN

    async def test_on_state_change_callback_ordering(self) -> None:
        """State change callbacks must fire in transition order."""
        transitions: list[tuple[str, State, State]] = []
        cfg = CircuitBreakerConfig(
            name="order",
            max_failures=1,
            timeout=0.01,
            on_state_change=lambda n, f, t: transitions.append((n, f, t)),
        )
        cb = CircuitBreaker(cfg)

        async def fail() -> None:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await cb.execute(fail)
        assert transitions == [("order", State.CLOSED, State.OPEN)]

        await asyncio.sleep(0.02)
        # Trigger lazy transition via state property
        _ = cb.state
        assert transitions[-1] == ("order", State.OPEN, State.HALF_OPEN)

        result = await cb.execute(lambda: asyncio.sleep(0, result=1))
        assert result == 1
        assert transitions[-1] == ("order", State.HALF_OPEN, State.CLOSED)
        assert len(transitions) == 3

    @pytest.mark.parametrize(
        "exc_class,msg",
        [
            (ValueError, "bad value"),
            (TypeError, "bad type"),
            (KeyError, "missing"),
            (OSError, "io error"),
            (AttributeError, "no attr"),
        ],
    )
    async def test_non_standard_exception_types(self, exc_class: type[Exception], msg: str) -> None:
        """Circuit breaker should count failures for any exception type."""
        cfg = CircuitBreakerConfig(name="exc-types", max_failures=1)
        cb = CircuitBreaker(cfg)

        async def fail() -> None:
            raise exc_class(msg)

        with pytest.raises(exc_class):
            await cb.execute(fail)
        assert cb.state == State.OPEN

    async def test_reset_during_half_open(self) -> None:
        """reset() while in HALF_OPEN should return to CLOSED."""
        cfg = CircuitBreakerConfig(name="reset-ho", max_failures=1, timeout=0.01)
        cb = CircuitBreaker(cfg)

        async def fail() -> None:
            raise RuntimeError("trip")

        with pytest.raises(RuntimeError):
            await cb.execute(fail)
        await asyncio.sleep(0.02)
        assert cb.state == State.HALF_OPEN

        cb.reset()
        assert cb.state == State.CLOSED
        assert cb.failures == 0

    async def test_zero_max_failures_opens_on_first_failure(self) -> None:
        """With max_failures=0, the first failure should NOT open the circuit
        because _on_failure checks failures >= max_failures after incrementing.
        Actually: failures starts at 0, after failure it's 1, and 1 >= 0 is True.
        Wait, let me re-read: the code increments first, then checks.
        So max_failures=0 means: after first failure, failures=1, 1>=0 → OPEN. But
        actually it will be open even with 0 failures since 0>=0 is true...
        Let me trace: _on_failure increments to 1, then checks 1 >= 0 → True → OPEN."""
        cfg = CircuitBreakerConfig(name="zero-mf", max_failures=0)
        cb = CircuitBreaker(cfg)

        async def fail() -> None:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await cb.execute(fail)
        assert cb.state == State.OPEN

    async def test_very_short_timeout_transitions_quickly(self) -> None:
        """Extremely short timeout should transition OPEN→HALF_OPEN almost immediately."""
        cfg = CircuitBreakerConfig(name="fast-to", max_failures=1, timeout=0.001)
        cb = CircuitBreaker(cfg)

        async def fail() -> None:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await cb.execute(fail)
        assert cb.state == State.OPEN
        await asyncio.sleep(0.01)
        assert cb.state == State.HALF_OPEN

    async def test_state_lazy_evaluation(self) -> None:
        """The state property performs lazy timeout check."""
        cfg = CircuitBreakerConfig(name="lazy", max_failures=1, timeout=0.01)
        cb = CircuitBreaker(cfg)

        async def fail() -> None:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await cb.execute(fail)

        # Internal state is OPEN
        assert cb._state == State.OPEN
        await asyncio.sleep(0.02)
        # Internal state still OPEN — no check has happened
        assert cb._state == State.OPEN
        # Accessing .state triggers lazy check
        assert cb.state == State.HALF_OPEN

    async def test_concurrent_execute_50_tasks(self) -> None:
        """50 concurrent tasks through a closed circuit should all succeed."""
        cb = CircuitBreaker(CircuitBreakerConfig(name="conc"))
        counter = 0

        async def inc() -> int:
            nonlocal counter
            counter += 1
            await asyncio.sleep(0.001)
            return counter

        results = await asyncio.gather(*[cb.execute(inc) for _ in range(50)])
        assert len(results) == 50
        assert cb.state == State.CLOSED
        assert cb.failures == 0

    async def test_rapid_open_close_cycling(self) -> None:
        """Rapidly cycling open/close under concurrent load should stay consistent."""
        transitions: list[tuple[State, State]] = []
        cfg = CircuitBreakerConfig(
            name="cycle",
            max_failures=2,
            timeout=0.01,
            half_open_max_calls=1,
            on_state_change=lambda n, f, t: transitions.append((f, t)),
        )
        cb = CircuitBreaker(cfg)

        call_count = 0

        async def flaky() -> int:
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:
                raise RuntimeError("flaky")
            return call_count

        # Run enough iterations to cycle the breaker
        for _ in range(10):
            try:  # noqa: SIM105
                await cb.execute(flaky)
            except (RuntimeError, CircuitOpenError):
                pass
            if cb.state == State.OPEN:
                await asyncio.sleep(0.02)

        # Verify all transitions are valid pairs
        valid_transitions = {
            (State.CLOSED, State.OPEN),
            (State.OPEN, State.HALF_OPEN),
            (State.HALF_OPEN, State.CLOSED),
            (State.HALF_OPEN, State.OPEN),
        }
        for t in transitions:
            assert t in valid_transitions, f"Invalid transition: {t}"


# ---------------------------------------------------------------------------
# 2. Retry Edge Cases
# ---------------------------------------------------------------------------


class TestRetryEdgeCases:
    async def test_exponential_backoff_growth(self) -> None:
        """Verify backoff delays grow exponentially."""
        delays: list[float] = []

        async def fail() -> None:
            raise RuntimeError("fail")

        def on_retry(attempt: int, exc: Exception, backoff: float) -> None:
            delays.append(backoff)

        cfg = RetryConfig(
            max_attempts=5,
            initial_backoff=0.01,
            backoff_factor=2.0,
            jitter=0.0,
            on_retry=on_retry,
        )

        with pytest.raises(RetryExhaustedError):
            await retry(fail, cfg)

        # Expected: 0.01, 0.02, 0.04, 0.08
        assert len(delays) == 4
        for i in range(1, len(delays)):
            ratio = delays[i] / delays[i - 1]
            assert 1.9 <= ratio <= 2.1, f"Ratio {ratio} not ~2.0 at index {i}"

    async def test_jitter_within_bounds(self) -> None:
        """Jitter should keep delays within ±jitter_range of the base backoff."""
        delays: list[float] = []

        async def fail() -> None:
            raise RuntimeError("fail")

        jitter = 0.5  # ±50% jitter

        cfg = RetryConfig(
            max_attempts=20,
            initial_backoff=0.001,
            backoff_factor=1.0,
            jitter=jitter,
            on_retry=lambda a, e, b: delays.append(b),
        )

        with pytest.raises(RetryExhaustedError):
            await retry(fail, cfg)

        base = 0.001
        for d in delays:
            jitter_range = base * jitter
            # Delay should be within [0, base + jitter_range] (clamped to 0)
            assert d >= 0.0, f"Delay {d} is negative"
            assert d <= base + jitter_range + 0.0001, f"Delay {d} exceeds max"

    @pytest.mark.parametrize(
        "exc_class,should_retry",
        [
            (ValueError, True),
            (TypeError, False),
            (KeyError, False),
        ],
    )
    async def test_retry_if_selective_filter(self, exc_class: type[Exception], should_retry: bool) -> None:
        """retry_if should only retry matching exception types."""
        calls = 0

        async def fail() -> None:
            nonlocal calls
            calls += 1
            raise exc_class("test")

        cfg = RetryConfig(
            max_attempts=3,
            initial_backoff=0.001,
            retry_if=lambda e: isinstance(e, ValueError),
        )

        if should_retry:
            with pytest.raises(RetryExhaustedError):
                await retry(fail, cfg)
            assert calls == 3
        else:
            with pytest.raises(exc_class):
                await retry(fail, cfg)
            assert calls == 1

    async def test_on_retry_receives_correct_attempt_and_error(self) -> None:
        """on_retry callback receives the attempt number, exception, and backoff."""
        records: list[tuple[int, str, float]] = []
        calls = 0

        async def fail() -> None:
            nonlocal calls
            calls += 1
            raise ValueError(f"err-{calls}")

        cfg = RetryConfig(
            max_attempts=4,
            initial_backoff=0.001,
            jitter=0.0,
            on_retry=lambda a, e, b: records.append((a, str(e), b)),
        )

        with pytest.raises(RetryExhaustedError):
            await retry(fail, cfg)

        assert len(records) == 3
        assert records[0][0] == 1
        assert "err-1" in records[0][1]
        assert records[1][0] == 2
        assert "err-2" in records[1][1]
        assert records[2][0] == 3
        assert "err-3" in records[2][1]
        # Backoffs should be positive
        for _, _, b in records:
            assert b > 0

    async def test_cancelled_error_stops_retries(self) -> None:
        """asyncio.CancelledError should propagate immediately without retrying."""
        calls = 0

        async def cancel_me() -> None:
            nonlocal calls
            calls += 1
            raise asyncio.CancelledError()

        cfg = RetryConfig(max_attempts=5, initial_backoff=0.001)

        with pytest.raises(asyncio.CancelledError):
            await retry(cancel_me, cfg)

        # CancelledError derives from BaseException, not Exception,
        # so it won't be caught by the generic except Exception handler.
        assert calls == 1

    async def test_max_backoff_capping(self) -> None:
        """Backoff should never exceed max_backoff."""
        delays: list[float] = []

        async def fail() -> None:
            raise RuntimeError("fail")

        cfg = RetryConfig(
            max_attempts=8,
            initial_backoff=0.5,
            max_backoff=1.0,
            backoff_factor=3.0,
            jitter=0.0,
            on_retry=lambda a, e, b: delays.append(b),
        )

        with pytest.raises(RetryExhaustedError):
            await retry(fail, cfg)

        for d in delays:
            assert d <= 1.0 + 0.001, f"Delay {d} exceeds max_backoff"

    async def test_max_attempts_one_no_retry(self) -> None:
        """max_attempts=1 means the function is called once with no retries."""
        calls = 0

        async def fail() -> None:
            nonlocal calls
            calls += 1
            raise RuntimeError("once")

        cfg = RetryConfig(max_attempts=1, initial_backoff=0.001)

        with pytest.raises(RetryExhaustedError) as exc_info:
            await retry(fail, cfg)

        assert calls == 1
        assert exc_info.value.attempts == 1

    async def test_retry_success_after_intermittent_failures(self) -> None:
        """Retry should return the successful result after intermittent failures."""
        calls = 0

        async def intermittent() -> str:
            nonlocal calls
            calls += 1
            if calls < 4:
                raise RuntimeError(f"fail-{calls}")
            return "recovered"

        cfg = RetryConfig(
            max_attempts=5,
            initial_backoff=0.001,
            jitter=0.0,
        )

        result = await retry(intermittent, cfg)
        assert result == "recovered"
        assert calls == 4


# ---------------------------------------------------------------------------
# 3. Bulkhead Edge Cases
# ---------------------------------------------------------------------------


class TestBulkheadEdgeCases:
    async def test_exactly_max_concurrent_all_succeed(self) -> None:
        """All tasks succeed when exactly at max_concurrent."""
        bh = Bulkhead(BulkheadConfig(name="exact", max_concurrent=5))
        barrier = asyncio.Barrier(5)

        async def task(idx: int) -> int:
            await barrier.wait()
            return idx

        results = await asyncio.gather(*[bh.execute(lambda i=i: task(i)) for i in range(5)])
        assert sorted(results) == [0, 1, 2, 3, 4]
        assert bh.available == 5
        assert bh.in_use == 0

    async def test_overflow_rejected(self) -> None:
        """Task N+1 gets BulkheadFullError when N slots are occupied."""
        bh = Bulkhead(BulkheadConfig(name="overflow", max_concurrent=3, max_wait=0))

        started = asyncio.Event()
        proceed = asyncio.Event()

        async def block() -> int:
            started.set()
            await proceed.wait()
            return 1

        # Fill all 3 slots
        holders = []
        for _ in range(3):
            started.clear()
            t = asyncio.create_task(bh.execute(block))
            holders.append(t)
            await started.wait()

        assert bh.available == 0
        assert bh.in_use == 3

        with pytest.raises(BulkheadFullError):
            await bh.execute(lambda: asyncio.sleep(0, result=99))

        proceed.set()
        await asyncio.gather(*holders)

    async def test_max_wait_timeout_precision(self) -> None:
        """max_wait should timeout within reasonable bounds."""
        bh = Bulkhead(BulkheadConfig(name="wait-prec", max_concurrent=1, max_wait=0.05))

        started = asyncio.Event()

        async def block() -> None:
            started.set()
            await asyncio.sleep(5.0)

        task = asyncio.create_task(bh.execute(block))
        await started.wait()

        start = time.monotonic()
        with pytest.raises(BulkheadFullError):
            await bh.execute(lambda: asyncio.sleep(0, result=1))
        elapsed = time.monotonic() - start

        assert 0.03 <= elapsed <= 0.2, f"Wait duration {elapsed} out of expected range"

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    async def test_slot_release_after_exception(self) -> None:
        """Slots must be released even when fn raises an exception."""
        bh = Bulkhead(BulkheadConfig(name="exc-release", max_concurrent=2))

        async def explode() -> None:
            raise ValueError("kaboom")

        for _ in range(5):
            with pytest.raises(ValueError):
                await bh.execute(explode)

        assert bh.available == 2
        assert bh.in_use == 0

        # Should still be able to use the bulkhead
        result = await bh.execute(lambda: asyncio.sleep(0, result=42))
        assert result == 42

    async def test_concurrent_acquire_release(self) -> None:
        """Concurrent acquire/release under load should keep state consistent."""
        bh = Bulkhead(BulkheadConfig(name="race", max_concurrent=5, max_wait=2.0))
        max_seen = 0
        lock = asyncio.Lock()

        async def work() -> None:
            nonlocal max_seen
            async with lock:
                if bh.in_use > max_seen:
                    max_seen = bh.in_use
            await asyncio.sleep(0.01)

        tasks = [asyncio.create_task(bh.execute(work)) for _ in range(20)]
        await asyncio.gather(*tasks)

        assert max_seen <= 5
        assert bh.available == 5
        assert bh.in_use == 0

    async def test_available_accuracy_during_execution(self) -> None:
        """available() should reflect actual free slots during active tasks."""
        bh = Bulkhead(BulkheadConfig(name="avail", max_concurrent=3))

        started = asyncio.Event()
        proceed = asyncio.Event()

        async def block() -> None:
            started.set()
            await proceed.wait()

        started.clear()
        t1 = asyncio.create_task(bh.execute(block))
        await started.wait()
        assert bh.available == 2

        started.clear()
        t2 = asyncio.create_task(bh.execute(block))
        await started.wait()
        assert bh.available == 1

        proceed.set()
        await asyncio.gather(t1, t2)
        assert bh.available == 3

    async def test_in_use_matches_running_tasks(self) -> None:
        """in_use should match the number of currently executing tasks."""
        bh = Bulkhead(BulkheadConfig(name="inuse", max_concurrent=5))

        started_count = 0
        all_started = asyncio.Event()
        proceed = asyncio.Event()

        async def block() -> None:
            nonlocal started_count
            started_count += 1
            if started_count == 3:
                all_started.set()
            await proceed.wait()

        tasks = [asyncio.create_task(bh.execute(block)) for _ in range(3)]
        await all_started.wait()

        assert bh.in_use == 3
        assert bh.available == 2

        proceed.set()
        await asyncio.gather(*tasks)
        assert bh.in_use == 0


# ---------------------------------------------------------------------------
# 4. Rate Limiter Edge Cases
# ---------------------------------------------------------------------------


class TestRateLimiterEdgeCases:
    async def test_burst_exhaustion_then_refill(self) -> None:
        """After burst is exhausted, wait() should block until tokens refill."""
        rl = RateLimiter(RateLimiterConfig(name="refill", rate=100.0, burst=3))

        for _ in range(3):
            assert rl.allow() is True
        assert rl.allow() is False

        start = time.monotonic()
        await rl.wait()
        elapsed = time.monotonic() - start
        # At 100 tokens/sec, 1 token takes ~0.01s
        assert elapsed >= 0.005, f"Refill too fast: {elapsed}"
        assert elapsed < 0.2, f"Refill too slow: {elapsed}"

    def test_token_refill_rate_accuracy(self) -> None:
        """Token refill should approximately match the configured rate."""
        rl = RateLimiter(RateLimiterConfig(name="rate-acc", rate=50.0, burst=10))

        # Drain all tokens
        for _ in range(10):
            rl.allow()
        assert rl.tokens < 1.0

        time.sleep(0.1)
        # After 0.1s at 50/s, ~5 tokens should have refilled
        tokens = rl.tokens
        assert 3.0 <= tokens <= 7.0, f"Expected ~5 tokens, got {tokens}"

    async def test_wait_cancellation(self) -> None:
        """Cancelling a wait() call should raise CancelledError."""
        rl = RateLimiter(RateLimiterConfig(name="cancel", rate=0.1, burst=1))
        rl.allow()  # exhaust the token

        async def slow_wait() -> None:
            await rl.wait()

        task = asyncio.create_task(slow_wait())
        await asyncio.sleep(0.05)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

    async def test_concurrent_execute_calls(self) -> None:
        """Concurrent execute calls should respect the burst limit."""
        rl = RateLimiter(RateLimiterConfig(name="conc-exec", rate=10.0, burst=5))

        successes = 0
        failures = 0

        async def inc() -> int:
            return 1

        tasks = []
        for _ in range(10):
            tasks.append(asyncio.create_task(rl.execute(inc)))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, RateLimitedError):
                failures += 1
            else:
                successes += 1

        assert successes == 5
        assert failures == 5

    def test_tokens_after_partial_consumption(self) -> None:
        """tokens property should reflect remaining after partial consumption."""
        rl = RateLimiter(RateLimiterConfig(name="partial", rate=10.0, burst=10))
        assert rl.tokens == 10.0

        for _ in range(4):
            rl.allow()

        remaining = rl.tokens
        assert 5.5 <= remaining <= 6.5, f"Expected ~6 tokens, got {remaining}"

    def test_very_high_rate_burst(self) -> None:
        """High rate (1000/s) with large burst should handle rapid allow() calls."""
        rl = RateLimiter(RateLimiterConfig(name="high", rate=1000.0, burst=500))
        allowed = sum(1 for _ in range(500) if rl.allow())
        assert allowed == 500
        assert rl.allow() is False

    async def test_multiple_sequential_waits(self) -> None:
        """Multiple sequential wait() calls should each succeed after refill."""
        rl = RateLimiter(RateLimiterConfig(name="seq-wait", rate=200.0, burst=1))
        rl.allow()  # exhaust

        for _ in range(3):
            start = time.monotonic()
            await rl.wait()
            elapsed = time.monotonic() - start
            assert elapsed < 0.2, f"Wait too long: {elapsed}"


# ---------------------------------------------------------------------------
# 5. Degradation Manager Edge Cases
# ---------------------------------------------------------------------------


class TestDegradationManagerEdgeCases:
    def test_feature_toggle_on_off(self) -> None:
        """Features can be toggled on and off."""
        dm = DegradationManager()
        assert dm.feature_enabled("beta") is False

        dm.set_feature("beta", True)
        assert dm.feature_enabled("beta") is True

        dm.set_feature("beta", False)
        assert dm.feature_enabled("beta") is False

    async def test_cb_state_change_integration_with_real_breaker(self) -> None:
        """on_circuit_breaker_state_change should track a real CB's state transitions."""
        dm = DegradationManager()
        callback = dm.on_circuit_breaker_state_change("payment-svc")

        cfg = CircuitBreakerConfig(
            name="payment",
            max_failures=2,
            timeout=0.01,
            on_state_change=callback,
        )
        cb = CircuitBreaker(cfg)

        async def fail() -> None:
            raise RuntimeError("down")

        # Trip the breaker
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.execute(fail)

        assert cb.state == State.OPEN
        assert dm.get_status("payment-svc").health == ServiceHealth.UNHEALTHY

        # Wait for half-open
        await asyncio.sleep(0.02)
        _ = cb.state  # trigger lazy transition
        assert dm.get_status("payment-svc").health == ServiceHealth.DEGRADED

        # Succeed to close
        result = await cb.execute(lambda: asyncio.sleep(0, result="ok"))
        assert result == "ok"
        assert cb.state == State.CLOSED
        assert dm.get_status("payment-svc").health == ServiceHealth.HEALTHY

    def test_health_check_mixed_services(self) -> None:
        """health_check should report degraded with per-service details."""
        dm = DegradationManager()
        dm.update_service("db", ServiceHealth.HEALTHY)
        dm.update_service("cache", ServiceHealth.UNHEALTHY, error="timeout")
        dm.update_service("api", ServiceHealth.DEGRADED, error="slow")

        result = dm.health_check()
        assert result["status"] == "degraded"
        assert result["services"]["db"]["health"] == ServiceHealth.HEALTHY
        assert result["services"]["cache"]["health"] == ServiceHealth.UNHEALTHY
        assert result["services"]["cache"]["error"] == "timeout"
        assert result["services"]["api"]["health"] == ServiceHealth.DEGRADED
        assert result["services"]["api"]["error"] == "slow"

    def test_concurrent_update_from_multiple_threads(self) -> None:
        """Concurrent update_service calls from multiple threads should not corrupt state."""
        dm = DegradationManager()
        errors: list[Exception] = []

        def updater(name: str, health: ServiceHealth) -> None:
            try:
                for _ in range(100):
                    dm.update_service(name, health)
                    dm.get_status(name)
                    dm.all_statuses()
                    dm.health_check()
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(10):
            health = ServiceHealth.HEALTHY if i % 2 == 0 else ServiceHealth.DEGRADED
            t = threading.Thread(target=updater, args=(f"svc-{i}", health))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"
        assert len(dm.all_statuses()) == 10

    def test_service_recovery_after_unhealthy(self) -> None:
        """Updating a service back to HEALTHY after UNHEALTHY should work."""
        dm = DegradationManager()

        dm.update_service("db", ServiceHealth.UNHEALTHY, error="connection lost")
        assert dm.is_healthy() is False
        assert dm.get_status("db").error == "connection lost"

        dm.update_service("db", ServiceHealth.HEALTHY)
        assert dm.is_healthy() is True
        assert dm.get_status("db").health == ServiceHealth.HEALTHY

    def test_unknown_service_returns_default_healthy(self) -> None:
        """Getting status of unknown service returns HEALTHY default."""
        dm = DegradationManager()
        status = dm.get_status("nonexistent")
        assert status.name == "nonexistent"
        assert status.health == ServiceHealth.HEALTHY
        assert status.error == ""
        assert status.last_check == 0.0


# ---------------------------------------------------------------------------
# 6. Multi-Pattern Integration Tests
# ---------------------------------------------------------------------------


class TestMultiPatternIntegration:
    async def test_cb_plus_retry_exhaustion_opens_circuit(self) -> None:
        """Retry exhaustion should trip the circuit breaker."""
        cfg = CircuitBreakerConfig(name="cb-retry", max_failures=3)
        cb = CircuitBreaker(cfg)
        call_count = 0

        async def flaky() -> str:
            nonlocal call_count
            call_count += 1
            raise RuntimeError(f"fail-{call_count}")

        retry_cfg = RetryConfig(max_attempts=2, initial_backoff=0.001, jitter=0.0)

        # Each retry call makes 2 attempts, each counted as a CB failure.
        # After 2 retry rounds (4 failures total), CB should be open.
        for _ in range(2):
            with pytest.raises(RetryExhaustedError):
                await cb.execute(lambda: retry(flaky, retry_cfg))

        assert cb.failures >= 2
        # The CB sees each retry(...) call as a single failure (it raises RetryExhaustedError).
        # After 2 failed executions through CB, we have 2 failures.
        # We need one more to hit max_failures=3.
        with pytest.raises(RetryExhaustedError):
            await cb.execute(lambda: retry(flaky, retry_cfg))

        assert cb.state == State.OPEN

    async def test_bulkhead_plus_rate_limiter(self) -> None:
        """Both bulkhead and rate limiter should enforce their limits."""
        bh = Bulkhead(BulkheadConfig(name="bh-rl", max_concurrent=3, max_wait=2.0))
        rl = RateLimiter(RateLimiterConfig(name="bh-rl", rate=10.0, burst=5))

        async def guarded() -> int:
            if not rl.allow():
                raise RateLimitedError("bh-rl")
            await asyncio.sleep(0.01)
            return 1

        tasks = [asyncio.create_task(bh.execute(guarded)) for _ in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        total_rate_limited = sum(1 for r in results if isinstance(r, RateLimitedError))
        total_success = sum(1 for r in results if r == 1)

        assert total_success + total_rate_limited == 10
        # Burst limit caps successful calls at 5
        assert total_success <= 5
        assert total_rate_limited >= 5

    async def test_full_composition_pipeline(self) -> None:
        """Compose rate_limiter → bulkhead → circuit_breaker → retry → fn."""
        rl = RateLimiter(RateLimiterConfig(name="pipe", rate=100.0, burst=20))
        bh = Bulkhead(BulkheadConfig(name="pipe", max_concurrent=5, max_wait=1.0))
        cb = CircuitBreaker(CircuitBreakerConfig(name="pipe", max_failures=10))
        retry_cfg = RetryConfig(max_attempts=2, initial_backoff=0.001, jitter=0.0)

        call_count = 0

        async def service() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        async def pipeline() -> str:
            await rl.wait()
            return await bh.execute(lambda: cb.execute(lambda: retry(service, retry_cfg)))

        results = await asyncio.gather(*[pipeline() for _ in range(10)])
        assert all(r == "ok" for r in results)
        assert call_count == 10

    async def test_degradation_recovery_scenario(self) -> None:
        """Service degrades, then recovers — health should track transitions."""
        dm = DegradationManager()
        callback = dm.on_circuit_breaker_state_change("api")

        cfg = CircuitBreakerConfig(name="api", max_failures=2, timeout=0.01, on_state_change=callback)
        cb = CircuitBreaker(cfg)

        # Phase 1: failures degrade the service
        async def fail() -> None:
            raise RuntimeError("down")

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.execute(fail)

        assert dm.get_status("api").health == ServiceHealth.UNHEALTHY
        assert dm.health_check()["status"] == "degraded"

        # Phase 2: wait for half-open
        await asyncio.sleep(0.02)
        _ = cb.state
        assert dm.get_status("api").health == ServiceHealth.DEGRADED

        # Phase 3: successful probe heals
        result = await cb.execute(lambda: asyncio.sleep(0, result="up"))
        assert result == "up"
        assert dm.get_status("api").health == ServiceHealth.HEALTHY
        assert dm.health_check()["status"] == "healthy"

    async def test_degradation_tracks_cb_under_load(self) -> None:
        """DegradationManager should track CB transitions during concurrent load."""
        dm = DegradationManager()
        callback = dm.on_circuit_breaker_state_change("load-svc")

        cfg = CircuitBreakerConfig(name="load", max_failures=5, timeout=0.02, on_state_change=callback)
        cb = CircuitBreaker(cfg)

        fail_count = 0

        async def sometimes_fail() -> str:
            nonlocal fail_count
            fail_count += 1
            if fail_count <= 5:
                raise RuntimeError("overloaded")
            return "ok"

        # Send 5 failures to trip the breaker
        for _ in range(5):
            with pytest.raises(RuntimeError):
                await cb.execute(sometimes_fail)

        assert cb.state == State.OPEN
        assert dm.get_status("load-svc").health == ServiceHealth.UNHEALTHY

        # Wait and recover
        await asyncio.sleep(0.03)
        assert cb.state == State.HALF_OPEN
        assert dm.get_status("load-svc").health == ServiceHealth.DEGRADED

        # Succeed to fully close
        result = await cb.execute(sometimes_fail)
        assert result == "ok"
        assert cb.state == State.CLOSED
        assert dm.get_status("load-svc").health == ServiceHealth.HEALTHY
