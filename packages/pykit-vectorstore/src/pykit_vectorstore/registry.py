"""Explicit vectorstore backend registry."""

from __future__ import annotations

from pykit_vectorstore.memory import InMemoryVectorStore
from pykit_vectorstore.store import VectorStore, VectorStoreConfig, VectorStoreError, VectorStoreFactory


class VectorStoreRegistry:
    """Injected registry mapping backend names to vectorstore factories."""

    def __init__(self) -> None:
        self._factories: dict[str, VectorStoreFactory] = {}

    def register(self, name: str, factory: VectorStoreFactory) -> None:
        """Register a backend factory."""
        if not name:
            raise VectorStoreError("vectorstore backend name is required")
        self._factories[name] = factory

    def create(self, config: VectorStoreConfig) -> VectorStore:
        """Construct the configured vectorstore backend."""
        try:
            factory = self._factories[config.backend]
        except KeyError as exc:
            raise VectorStoreError(f"vectorstore backend '{config.backend}' is not registered") from exc
        return factory(config)

    def names(self) -> tuple[str, ...]:
        """Return registered backend names."""
        return tuple(sorted(self._factories))


def register_memory(registry: VectorStoreRegistry) -> None:
    """Register the in-memory vectorstore backend."""
    registry.register("memory", lambda config: InMemoryVectorStore())


def default_vectorstore_registry() -> VectorStoreRegistry:
    """Return a new registry containing only lean core defaults."""
    registry = VectorStoreRegistry()
    register_memory(registry)
    return registry
