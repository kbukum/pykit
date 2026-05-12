"""Explicit storage backend registry."""

from __future__ import annotations

from collections.abc import Callable

from pykit_errors import AppError
from pykit_errors.codes import ErrorCode
from pykit_storage.base import Storage
from pykit_storage.config import StorageConfig
from pykit_storage.local import LocalStorage

StorageFactory = Callable[[StorageConfig], Storage]


class StorageRegistry:
    """Injected storage backend registry."""

    def __init__(self) -> None:
        self._factories: dict[str, StorageFactory] = {}

    def register(self, name: str, factory: StorageFactory) -> None:
        """Register a storage backend factory."""
        if not name:
            raise AppError(ErrorCode.INVALID_INPUT, "storage provider name is required")
        self._factories[name] = factory

    def create(self, config: StorageConfig) -> Storage:
        """Construct the configured storage backend."""
        try:
            factory = self._factories[config.provider]
        except KeyError as exc:
            raise AppError(
                ErrorCode.INVALID_INPUT,
                f"storage provider '{config.provider}' is not registered",
            ) from exc
        return factory(config)

    def names(self) -> tuple[str, ...]:
        """Return registered backend names."""
        return tuple(sorted(self._factories))


def register_local(registry: StorageRegistry) -> None:
    """Register local filesystem storage."""
    registry.register(
        "local",
        lambda config: LocalStorage(base_path=config.base_path, public_url=config.public_url),
    )


def default_storage_registry() -> StorageRegistry:
    """Return a new registry containing only lean core defaults."""
    registry = StorageRegistry()
    register_local(registry)
    return registry
