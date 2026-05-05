"""Explicit messaging adapter registry."""

from __future__ import annotations

from collections.abc import Callable

from pykit_errors import AppError
from pykit_messaging.config import BrokerConfig
from pykit_messaging.protocols import MessageConsumer, MessageProducer

ProducerFactory = Callable[[BrokerConfig], MessageProducer]
ConsumerFactory = Callable[[BrokerConfig], MessageConsumer]
AdapterStateCleanup = Callable[[], None]


class MessagingRegistry:
    """Application-owned messaging adapter registry.

    Adapters are registered explicitly by composition code. Registration is
    config-free; each create call selects the adapter from ``config.adapter``
    and passes the full config to the registered factory.
    """

    def __init__(self) -> None:
        self._producers: dict[str, ProducerFactory] = {}
        self._consumers: dict[str, ConsumerFactory] = {}
        self._state_cleanups: dict[str, AdapterStateCleanup] = {}

    def register_producer(self, adapter: str, factory: ProducerFactory) -> None:
        """Register a producer factory for *adapter*."""
        if not adapter:
            raise AppError.invalid_input("adapter", "messaging adapter name is required")
        if adapter in self._producers:
            raise AppError.already_exists(f"messaging producer adapter '{adapter}'")
        self._producers[adapter] = factory

    def register_consumer(self, adapter: str, factory: ConsumerFactory) -> None:
        """Register a consumer factory for *adapter*."""
        if not adapter:
            raise AppError.invalid_input("adapter", "messaging adapter name is required")
        if adapter in self._consumers:
            raise AppError.already_exists(f"messaging consumer adapter '{adapter}'")
        self._consumers[adapter] = factory

    def register_adapter_state_cleanup(self, adapter: str, cleanup: AdapterStateCleanup) -> None:
        """Register a callback that clears per-adapter runtime state."""
        if not adapter:
            raise AppError.invalid_input("adapter", "messaging adapter name is required")
        self._state_cleanups[adapter] = cleanup

    def clear_adapter_state(self, adapter: str | None = None) -> None:
        """Clear runtime state for one adapter, or all adapters when omitted."""
        if adapter is None:
            for cleanup in self._state_cleanups.values():
                cleanup()
            return
        selected_cleanup = self._state_cleanups.get(adapter)
        if selected_cleanup is not None:
            selected_cleanup()

    def producer(self, config: BrokerConfig) -> MessageProducer:
        """Create a producer for ``config.adapter`` using *config*."""
        config.validate()
        if not config.enabled:
            raise AppError.invalid_input("enabled", "messaging adapter config is disabled")
        try:
            factory = self._producers[config.adapter]
        except KeyError as exc:
            raise AppError.not_found(f"messaging producer adapter '{config.adapter}'") from exc
        return factory(config)

    def consumer(self, config: BrokerConfig) -> MessageConsumer:
        """Create a consumer for ``config.adapter`` using *config*."""
        config.validate()
        if not config.enabled:
            raise AppError.invalid_input("enabled", "messaging adapter config is disabled")
        try:
            factory = self._consumers[config.adapter]
        except KeyError as exc:
            raise AppError.not_found(f"messaging consumer adapter '{config.adapter}'") from exc
        return factory(config)

    def producer_adapters(self) -> list[str]:
        """Return registered producer adapter names."""
        return sorted(self._producers)

    def consumer_adapters(self) -> list[str]:
        """Return registered consumer adapter names."""
        return sorted(self._consumers)
