"""Explicit messaging backend registry."""

from __future__ import annotations

from collections.abc import Callable

from pykit_errors import AppError
from pykit_messaging.config import BrokerConfig
from pykit_messaging.protocols import MessageConsumer, MessageProducer

ProducerFactory = Callable[[BrokerConfig], MessageProducer]
ConsumerFactory = Callable[[BrokerConfig], MessageConsumer]
BackendStateCleanup = Callable[[], None]


class MessagingRegistry:
    """Application-owned messaging backend registry.

    Backends are registered explicitly by composition code. Registration is
    config-free; each create call selects the backend from ``config.backend``
    and passes the full config to the registered factory.
    """

    def __init__(self) -> None:
        self._producers: dict[str, ProducerFactory] = {}
        self._consumers: dict[str, ConsumerFactory] = {}
        self._state_cleanups: dict[str, BackendStateCleanup] = {}

    def register_producer(self, backend: str, factory: ProducerFactory) -> None:
        """Register a producer factory for *backend*."""
        if not backend:
            raise AppError.invalid_input("backend", "messaging backend name is required")
        if backend in self._producers:
            raise AppError.already_exists(f"messaging producer backend '{backend}'")
        self._producers[backend] = factory

    def register_consumer(self, backend: str, factory: ConsumerFactory) -> None:
        """Register a consumer factory for *backend*."""
        if not backend:
            raise AppError.invalid_input("backend", "messaging backend name is required")
        if backend in self._consumers:
            raise AppError.already_exists(f"messaging consumer backend '{backend}'")
        self._consumers[backend] = factory

    def register_backend_state_cleanup(self, backend: str, cleanup: BackendStateCleanup) -> None:
        """Register a callback that clears per-backend runtime state."""
        if not backend:
            raise AppError.invalid_input("backend", "messaging backend name is required")
        self._state_cleanups[backend] = cleanup

    def clear_backend_state(self, backend: str | None = None) -> None:
        """Clear runtime state for one backend, or all backends when omitted."""
        if backend is None:
            for cleanup in self._state_cleanups.values():
                cleanup()
            return
        selected_cleanup = self._state_cleanups.get(backend)
        if selected_cleanup is not None:
            selected_cleanup()

    def producer(self, config: BrokerConfig) -> MessageProducer:
        """Create a producer for ``config.backend`` using *config*."""
        config.validate()
        if not config.enabled:
            raise AppError.invalid_input("enabled", "messaging backend config is disabled")
        try:
            factory = self._producers[config.backend]
        except KeyError as exc:
            raise AppError.not_found(f"messaging producer backend '{config.backend}'") from exc
        return factory(config)

    def consumer(self, config: BrokerConfig) -> MessageConsumer:
        """Create a consumer for ``config.backend`` using *config*."""
        config.validate()
        if not config.enabled:
            raise AppError.invalid_input("enabled", "messaging backend config is disabled")
        try:
            factory = self._consumers[config.backend]
        except KeyError as exc:
            raise AppError.not_found(f"messaging consumer backend '{config.backend}'") from exc
        return factory(config)

    def producer_backends(self) -> list[str]:
        """Return registered producer backend names."""
        return sorted(self._producers)

    def consumer_backends(self) -> list[str]:
        """Return registered consumer backend names."""
        return sorted(self._consumers)
