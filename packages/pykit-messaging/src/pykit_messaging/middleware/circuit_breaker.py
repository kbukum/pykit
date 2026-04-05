"""Circuit breaker middleware for message handlers."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from pykit_messaging.handler import MessageHandlerProtocol
from pykit_messaging.types import Message

logger = logging.getLogger(__name__)


class CircuitState(StrEnum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"


class CircuitOpenError(Exception):
    """Raised when the circuit breaker is open and the message is rejected."""

    def __init__(self) -> None:
        super().__init__("Circuit breaker is open")


@dataclass(frozen=True)
class CircuitBreakerConfig:
    """Configuration for the circuit breaker middleware.

    Args:
        threshold: Consecutive failures required to trip the circuit open.
        timeout: Seconds to wait before transitioning from open to half-open.
        half_open_max: Maximum probe requests allowed in the half-open state.
    """

    threshold: int = 5
    timeout: float = 30.0
    half_open_max: int = 2


class CircuitBreakerHandler:
    """Fails fast when the downstream handler is unhealthy.

    Implements the classic circuit breaker pattern with three states:
      - **CLOSED**: Normal operation, requests pass through.
      - **OPEN**: Downstream unhealthy, requests are rejected immediately.
      - **HALF_OPEN**: Recovery probe, limited requests allowed.

    Args:
        inner: The handler to delegate to when the circuit is not open.
        config: Optional circuit breaker configuration; defaults to
            ``CircuitBreakerConfig()``.
    """

    def __init__(
        self,
        inner: MessageHandlerProtocol,
        config: CircuitBreakerConfig | None = None,
    ) -> None:
        self._inner = inner
        self._config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._successes = 0
        self._half_open_calls = 0
        self._last_failure_time: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Current circuit breaker state."""
        self._check_timeout()
        return self._state

    async def handle(self, msg: Message) -> None:
        """Handle a message through the circuit breaker.

        Args:
            msg: The message to handle.

        Raises:
            CircuitOpenError: If the circuit is open or half-open limit reached.
        """
        async with self._lock:
            if not self._allow_request():
                raise CircuitOpenError
        try:
            await self._inner.handle(msg)
        except Exception:
            async with self._lock:
                self._on_failure()
            raise
        else:
            async with self._lock:
                self._on_success()

    def _allow_request(self) -> bool:
        """Determine whether a request should be allowed through."""
        self._check_timeout()
        if self._state == CircuitState.CLOSED:
            return True
        if self._state == CircuitState.OPEN:
            return False
        # HALF_OPEN
        if self._half_open_calls < self._config.half_open_max:
            self._half_open_calls += 1
            return True
        return False

    def _on_success(self) -> None:
        """Record a successful call."""
        self._check_timeout()
        if self._state == CircuitState.CLOSED:
            self._failures = 0
        elif self._state == CircuitState.HALF_OPEN:
            self._successes += 1
            if self._successes >= self._config.half_open_max:
                self._to_state(CircuitState.CLOSED)

    def _on_failure(self) -> None:
        """Record a failed call."""
        self._failures += 1
        self._last_failure_time = time.monotonic()
        self._check_timeout()
        if self._state == CircuitState.CLOSED:
            if self._failures >= self._config.threshold:
                self._to_state(CircuitState.OPEN)
        elif self._state == CircuitState.HALF_OPEN:
            self._to_state(CircuitState.OPEN)

    def _check_timeout(self) -> None:
        """Transition from OPEN to HALF_OPEN if timeout has elapsed."""
        if (
            self._state == CircuitState.OPEN
            and self._last_failure_time > 0
            and (time.monotonic() - self._last_failure_time) >= self._config.timeout
        ):
            self._to_state(CircuitState.HALF_OPEN)

    def _to_state(self, to: CircuitState) -> None:
        """Transition to a new state."""
        if self._state == to:
            return
        old = self._state
        self._state = to
        self._half_open_calls = 0
        self._successes = 0
        if to == CircuitState.CLOSED:
            self._failures = 0
        logger.info("Circuit breaker: %s -> %s", old, to)


def circuit_breaker(
    config: CircuitBreakerConfig | None = None,
) -> Callable[[MessageHandlerProtocol], MessageHandlerProtocol]:
    """Return a middleware function implementing the circuit breaker pattern.

    Args:
        config: Optional circuit breaker configuration.

    Returns:
        A middleware function compatible with ``chain_handlers``.
    """

    def _middleware(inner: MessageHandlerProtocol) -> MessageHandlerProtocol:
        return CircuitBreakerHandler(inner, config)

    return _middleware
