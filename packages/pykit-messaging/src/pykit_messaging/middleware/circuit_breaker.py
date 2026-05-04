"""Circuit breaker middleware for message handlers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pykit_messaging.handler import MessageHandlerProtocol
from pykit_messaging.types import Message
from pykit_resilience import (
    CircuitBreaker,
    CircuitOpenError,
)
from pykit_resilience import (
    CircuitBreakerConfig as ResilienceCircuitBreakerConfig,
)
from pykit_resilience import (
    State as CircuitState,
)


@dataclass(frozen=True)
class CircuitBreakerConfig:
    """Configuration for the circuit breaker middleware."""

    threshold: int = 5
    timeout: float = 30.0
    half_open_max: int = 2
    name: str = "messaging-handler"
    on_state_change: Callable[[str, CircuitState, CircuitState], None] | None = None

    def to_resilience_config(self) -> ResilienceCircuitBreakerConfig:
        """Convert to the canonical resilience circuit breaker config."""
        return ResilienceCircuitBreakerConfig(
            name=self.name,
            max_failures=self.threshold,
            timeout=self.timeout,
            half_open_max_calls=self.half_open_max,
            on_state_change=self.on_state_change,
        )


class CircuitBreakerHandler:
    """Fails fast when the downstream handler is unhealthy."""

    def __init__(
        self,
        inner: MessageHandlerProtocol,
        config: CircuitBreakerConfig | None = None,
    ) -> None:
        self._inner = inner
        self._config = config or CircuitBreakerConfig()
        self._breaker = CircuitBreaker(self._config.to_resilience_config())

    @property
    def state(self) -> CircuitState:
        """Current circuit breaker state."""
        return self._breaker.state

    @property
    def failures(self) -> int:
        """Current failure count."""
        return self._breaker.failures

    async def handle(self, msg: Message) -> None:
        """Handle a message through the canonical circuit breaker."""

        async def _handle() -> None:
            await self._inner.handle(msg)

        await self._breaker.execute(_handle)


def circuit_breaker(
    config: CircuitBreakerConfig | None = None,
) -> Callable[[MessageHandlerProtocol], MessageHandlerProtocol]:
    """Return a middleware function implementing canonical circuit breaking."""

    def _middleware(inner: MessageHandlerProtocol) -> MessageHandlerProtocol:
        return CircuitBreakerHandler(inner, config)

    return _middleware


__all__ = [
    "CircuitBreakerConfig",
    "CircuitBreakerHandler",
    "CircuitOpenError",
    "CircuitState",
    "circuit_breaker",
]
