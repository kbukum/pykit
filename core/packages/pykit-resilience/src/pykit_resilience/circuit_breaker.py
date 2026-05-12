"""Circuit breaker pattern for fault tolerance."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeVar

from pykit_errors import AppError
from pykit_errors.codes import ErrorCode

T = TypeVar("T")


class State(StrEnum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"


class CircuitOpenError(AppError):
    """Raised when the circuit breaker is open."""

    def __init__(self, name: str) -> None:
        super().__init__(ErrorCode.SERVICE_UNAVAILABLE, f"Circuit breaker '{name}' is open")


@dataclass
class CircuitBreakerConfig:
    """Configuration for a circuit breaker."""

    name: str = "default"
    max_failures: int = 5
    timeout: float = 30.0
    half_open_max_calls: int = 1
    on_state_change: Callable[[str, State, State], None] | None = None


class CircuitBreaker:
    """Circuit breaker prevents cascading failures by failing fast.

    States:
      - CLOSED: Normal operation, requests pass through
      - OPEN: Service is unhealthy, requests fail immediately
      - HALF_OPEN: Testing recovery, limited requests allowed
    """

    def __init__(self, config: CircuitBreakerConfig | None = None) -> None:
        self._config = config or CircuitBreakerConfig()
        self._state = State.CLOSED
        self._failures = 0
        self._successes = 0
        self._half_open_calls = 0
        self._last_failure_time: float = 0.0
        self._lock = asyncio.Lock()

    async def execute(self, fn: Callable[[], Awaitable[T]]) -> T:
        """Run fn through the circuit breaker."""
        async with self._lock:
            if not self._allow_request():
                raise CircuitOpenError(self._config.name)
        try:
            result = await fn()
        except Exception as exc:
            async with self._lock:
                self._on_failure()
            raise exc
        else:
            async with self._lock:
                self._on_success()
            return result

    @property
    def state(self) -> State:
        """Current circuit breaker state."""
        self._check_timeout()
        return self._state

    def reset(self) -> None:
        """Reset the circuit breaker to closed state."""
        self._to_state(State.CLOSED)
        self._failures = 0
        self._successes = 0
        self._half_open_calls = 0

    @property
    def failures(self) -> int:
        """Current failure count."""
        return self._failures

    def _allow_request(self) -> bool:
        self._check_timeout()
        if self._state == State.CLOSED:
            return True
        if self._state == State.OPEN:
            return False
        if self._state == State.HALF_OPEN:
            if self._half_open_calls < self._config.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False
        return False

    def _on_success(self) -> None:
        self._check_timeout()
        if self._state == State.CLOSED:
            self._failures = 0
        elif self._state == State.HALF_OPEN:
            self._successes += 1
            if self._successes >= self._config.half_open_max_calls:
                self._to_state(State.CLOSED)

    def _on_failure(self) -> None:
        self._failures += 1
        self._last_failure_time = time.monotonic()
        self._check_timeout()
        if self._state == State.CLOSED:
            if self._failures >= self._config.max_failures:
                self._to_state(State.OPEN)
        elif self._state == State.HALF_OPEN:
            self._to_state(State.OPEN)

    def _check_timeout(self) -> None:
        if (
            self._state == State.OPEN
            and self._last_failure_time > 0
            and (time.monotonic() - self._last_failure_time) >= self._config.timeout
        ):
            self._to_state(State.HALF_OPEN)

    def _to_state(self, to: State) -> None:
        if self._state == to:
            return
        from_state = self._state
        self._state = to
        self._half_open_calls = 0
        self._successes = 0
        if to == State.CLOSED:
            self._failures = 0
        if self._config.on_state_change is not None:
            self._config.on_state_change(self._config.name, from_state, to)
