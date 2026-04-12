"""Provider factory registry — config-driven provider selection.

Mirrors gokit's ``init()``-based factory registration and rskit's
``register_provider``/``create_provider`` pattern.  Services never
import provider packages directly — the factory resolves the correct
implementation from ``DiscoveryConfig.provider``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from pykit_discovery.config import DiscoveryConfig
    from pykit_discovery.protocols import Discovery, Registry

logger = logging.getLogger(__name__)


class ProviderPair:
    """Holds the generic registry and discovery interfaces for a provider."""

    __slots__ = ("registry", "discovery", "_closeable")

    def __init__(
        self,
        registry: Registry,
        discovery: Discovery,
        closeable: Any | None = None,
    ) -> None:
        self.registry = registry
        self.discovery = discovery
        self._closeable = closeable

    async def close(self) -> None:
        """Close underlying resources if the provider supports it."""
        if self._closeable is not None and hasattr(self._closeable, "close"):
            await self._closeable.close()


class ProviderFactory(Protocol):
    """Callable that creates a ``ProviderPair`` from a ``DiscoveryConfig``."""

    def __call__(self, config: DiscoveryConfig) -> ProviderPair: ...


# Global factory registry
_registry: dict[str, ProviderFactory] = {}


def register_provider(name: str, factory: ProviderFactory) -> None:
    """Register a provider factory under the given name.

    Raises ``ValueError`` if the name is already registered.
    """
    if name in _registry:
        raise ValueError(f"discovery provider {name!r} already registered")
    _registry[name] = factory
    logger.debug("registered discovery provider %r", name)


def create_provider(config: DiscoveryConfig) -> ProviderPair:
    """Look up the provider by ``config.provider`` and create it.

    Raises ``KeyError`` if no factory is registered for the provider name.
    """
    factory = _registry.get(config.provider)
    if factory is None:
        available = ", ".join(sorted(_registry)) or "(none)"
        raise KeyError(
            f"unknown discovery provider {config.provider!r}; "
            f"available: {available}"
        )
    return factory(config)


# ── Built-in provider factories ───────────────────────────────────────


def _static_factory(config: DiscoveryConfig) -> ProviderPair:
    """Create a StaticProvider pre-populated from ``static_endpoints``."""
    from pykit_discovery.static import StaticProvider
    from pykit_discovery.types import ServiceInstance

    provider = StaticProvider()
    # Synchronously populate — StaticProvider is in-memory
    for ep in config.static_endpoints:
        inst = ServiceInstance(
            id=f"{ep.name}-static",
            name=ep.name,
            host=ep.address,
            port=ep.port,
            protocol=ep.protocol,
            tags=list(ep.tags),
            metadata=dict(ep.metadata),
            weight=ep.weight,
            healthy=ep.healthy,
        )
        # StaticProvider._services is a plain dict — safe to populate directly
        if inst.name not in provider._services:
            provider._services[inst.name] = {}
        provider._services[inst.name][inst.id] = inst

    return ProviderPair(registry=provider, discovery=provider)


def _consul_factory(config: DiscoveryConfig) -> ProviderPair:
    """Create a ConsulProvider from generic config fields."""
    from pykit_discovery.consul import ConsulProvider

    provider = ConsulProvider(
        address=config.addr or "localhost:8500",
        scheme=config.scheme or "http",
        token=config.token or None,
        dc=config.provider_options.get("dc"),
    )
    return ProviderPair(
        registry=provider,
        discovery=provider,
        closeable=provider,
    )


def init_builtin() -> None:
    """Register all built-in providers.  Safe to call multiple times."""
    if "static" not in _registry:
        register_provider("static", _static_factory)
    if "consul" not in _registry:
        register_provider("consul", _consul_factory)
