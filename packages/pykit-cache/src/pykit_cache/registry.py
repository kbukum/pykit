"""Explicit cache backend registry."""

from __future__ import annotations

from pykit_cache.backends import CacheBackend, CacheFactory, InMemoryCache
from pykit_cache.config import CacheConfig
from pykit_errors import AppError
from pykit_errors.codes import ErrorCode


class CacheRegistry:
    """Injected registry mapping backend names to factories."""

    def __init__(self) -> None:
        self._factories: dict[str, CacheFactory] = {}

    def register(self, name: str, factory: CacheFactory) -> None:
        """Register a backend factory under ``name``."""
        if not name:
            raise AppError(ErrorCode.INVALID_INPUT, "cache backend name is required")
        self._factories[name] = factory

    def create(self, config: CacheConfig) -> CacheBackend:
        """Construct the configured backend."""
        try:
            factory = self._factories[config.backend]
        except KeyError as exc:
            raise AppError(
                ErrorCode.INVALID_INPUT,
                f"cache backend '{config.backend}' is not registered",
            ) from exc
        return factory(config)

    def names(self) -> tuple[str, ...]:
        """Return registered backend names."""
        return tuple(sorted(self._factories))


def register_memory(registry: CacheRegistry) -> None:
    """Register the lean in-memory cache backend."""
    registry.register(
        "memory",
        lambda config: InMemoryCache(
            default_ttl_seconds=config.default_ttl_seconds,
            max_entries=config.max_entries,
        ),
    )


def default_cache_registry() -> CacheRegistry:
    """Return a new registry containing only lean core defaults."""
    registry = CacheRegistry()
    register_memory(registry)
    return registry
