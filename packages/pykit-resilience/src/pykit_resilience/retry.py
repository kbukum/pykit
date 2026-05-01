"""Retry pattern with configurable backoff strategies."""

from __future__ import annotations

import asyncio
import math
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from pykit_errors import AppError
from pykit_errors.codes import ErrorCode


class RetryExhaustedError(AppError):
    """Raised when all retry attempts are exhausted."""

    def __init__(self, attempts: int, last_error: Exception) -> None:
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(
            ErrorCode.SERVICE_UNAVAILABLE,
            f"All {attempts} retry attempts exhausted, last error: {last_error}",
        )


class BackoffStrategy(Protocol):
    """Strategy for computing retry backoff durations."""

    def calculate(self, attempt: int, config: RetryConfig) -> float:
        """Return the backoff delay for *attempt*."""


@dataclass(frozen=True)
class ExponentialBackoff:
    """Backoff strategy that grows exponentially per retry attempt."""

    def calculate(self, attempt: int, config: RetryConfig) -> float:
        return config.initial_backoff * math.pow(config.backoff_factor, attempt - 1)


@dataclass(frozen=True)
class ConstantBackoff:
    """Backoff strategy that uses a constant delay for each retry."""

    def calculate(self, attempt: int, config: RetryConfig) -> float:
        del attempt
        return config.initial_backoff


@dataclass(frozen=True)
class LinearBackoff:
    """Backoff strategy that grows linearly with each retry attempt."""

    def calculate(self, attempt: int, config: RetryConfig) -> float:
        return config.initial_backoff * attempt


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    initial_backoff: float = 0.1
    max_backoff: float = 10.0
    backoff_factor: float = 2.0
    jitter: float = 0.1
    retry_if: Callable[[Exception], bool] | None = None
    on_retry: Callable[[int, Exception, float], None] | None = None
    backoff_strategy: BackoffStrategy | None = None


def _calculate_backoff(attempt: int, config: RetryConfig) -> float:
    """Calculate backoff duration with the configured strategy and jitter."""
    strategy = config.backoff_strategy or ExponentialBackoff()
    backoff = strategy.calculate(attempt, config)
    if config.jitter > 0:
        jitter_range = backoff * config.jitter
        backoff += random.uniform(-jitter_range, jitter_range)
    backoff = min(backoff, config.max_backoff)
    return max(backoff, 0.0)


async def retry[T](
    fn: Callable[[], Awaitable[T]],
    config: RetryConfig | None = None,
) -> T:
    """Execute fn with retry logic using exponential backoff + jitter.

    Returns the result of fn or raises RetryExhaustedError if all attempts fail.
    """
    cfg = config or RetryConfig()
    last_error: Exception | None = None

    for attempt in range(1, cfg.max_attempts + 1):
        try:
            return await fn()
        except Exception as exc:
            last_error = exc
            if cfg.retry_if is not None and not cfg.retry_if(exc):
                raise
            if attempt == cfg.max_attempts:
                break
            backoff = _calculate_backoff(attempt, cfg)
            if cfg.on_retry is not None:
                cfg.on_retry(attempt, exc, backoff)
            await asyncio.sleep(backoff)

    raise RetryExhaustedError(cfg.max_attempts, last_error) from last_error  # type: ignore[arg-type]
