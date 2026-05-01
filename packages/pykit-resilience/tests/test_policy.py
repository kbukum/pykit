"""Tests for policy composition and backoff strategies."""

from __future__ import annotations

import asyncio

import pytest

from pykit_resilience import (
    ConstantBackoff,
    LinearBackoff,
    Policy,
    PolicyConfig,
    RateLimitedError,
    RateLimiterConfig,
    RetryConfig,
    RetryExhaustedError,
    retry,
)


class TestBackoffStrategies:
    def test_constant_backoff_repeats_initial_delay(self) -> None:
        config = RetryConfig(
            initial_backoff=0.25,
            max_backoff=1.0,
            jitter=0.0,
            backoff_strategy=ConstantBackoff(),
        )
        assert config.backoff_strategy is not None
        assert config.backoff_strategy.calculate(1, config) == 0.25
        assert config.backoff_strategy.calculate(4, config) == 0.25

    def test_linear_backoff_scales_by_attempt(self) -> None:
        config = RetryConfig(
            initial_backoff=0.2,
            max_backoff=10.0,
            jitter=0.0,
            backoff_strategy=LinearBackoff(),
        )
        assert config.backoff_strategy is not None
        assert config.backoff_strategy.calculate(1, config) == pytest.approx(0.2)
        assert config.backoff_strategy.calculate(3, config) == pytest.approx(0.6)

    @pytest.mark.asyncio
    async def test_retry_uses_linear_backoff_strategy(self) -> None:
        attempts = 0
        delays: list[float] = []

        async def fn() -> str:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise RuntimeError("retry me")
            return "ok"

        result = await retry(
            fn,
            RetryConfig(
                max_attempts=3,
                initial_backoff=0.01,
                jitter=0.0,
                backoff_strategy=LinearBackoff(),
                on_retry=lambda _attempt, _error, backoff: delays.append(backoff),
            ),
        )

        assert result == "ok"
        assert delays == [0.01, 0.02]


class TestPolicy:
    @pytest.mark.asyncio
    async def test_policy_retries_inside_timeout(self) -> None:
        attempts = 0
        policy = Policy(
            PolicyConfig(
                retry=RetryConfig(max_attempts=3, initial_backoff=0.0, jitter=0.0),
                timeout=1.0,
            )
        )

        async def flaky() -> str:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise RuntimeError("boom")
            return "done"

        assert await policy.execute(flaky) == "done"
        assert attempts == 3

    @pytest.mark.asyncio
    async def test_policy_times_out_after_retries_start(self) -> None:
        policy = Policy(
            PolicyConfig(
                retry=RetryConfig(max_attempts=5, initial_backoff=0.0, jitter=0.0),
                timeout=0.05,
            )
        )

        async def slow_failure() -> None:
            await asyncio.sleep(0.03)
            raise RuntimeError("slow")

        with pytest.raises(TimeoutError):
            await policy.execute(slow_failure)

    @pytest.mark.asyncio
    async def test_policy_applies_rate_limit_before_retry(self) -> None:
        policy = Policy(
            PolicyConfig(
                rate_limiter=RateLimiterConfig(name="policy", rate=100.0, burst=1),
                retry=RetryConfig(max_attempts=3, initial_backoff=0.0, jitter=0.0),
            )
        )

        async def ok() -> int:
            return 1

        assert await policy.execute(ok) == 1
        with pytest.raises(RateLimitedError):
            await policy.execute(ok)

    @pytest.mark.asyncio
    async def test_policy_does_not_retry_circuit_open_errors(self) -> None:
        attempts = 0
        policy = Policy(
            PolicyConfig(
                retry=RetryConfig(max_attempts=3, initial_backoff=0.0, jitter=0.0),
                circuit_breaker=None,
            )
        )

        async def always_fail() -> None:
            nonlocal attempts
            attempts += 1
            raise RuntimeError("always")

        with pytest.raises(RetryExhaustedError):
            await policy.execute(always_fail)
        assert attempts == 3
