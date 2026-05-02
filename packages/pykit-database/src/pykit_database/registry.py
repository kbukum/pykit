"""Explicit database backend registry."""

from __future__ import annotations

from collections.abc import Callable

from pykit_database.config import DatabaseConfig
from pykit_database.database import Database
from pykit_errors import AppError
from pykit_errors.codes import ErrorCode

DatabaseFactory = Callable[[DatabaseConfig], Database]


class DatabaseRegistry:
    """Injected registry for database backend factories."""

    def __init__(self) -> None:
        self._factories: dict[str, DatabaseFactory] = {}

    def register(self, name: str, factory: DatabaseFactory) -> None:
        """Register a database backend factory."""
        if not name:
            raise AppError(ErrorCode.INVALID_INPUT, "database backend name is required")
        self._factories[name] = factory

    def create(self, config: DatabaseConfig) -> Database:
        """Construct the configured database backend."""
        try:
            factory = self._factories[config.backend]
        except KeyError as exc:
            raise AppError(
                ErrorCode.INVALID_INPUT,
                f"database backend '{config.backend}' is not registered",
            ) from exc
        return factory(config)

    def names(self) -> tuple[str, ...]:
        """Return registered backend names."""
        return tuple(sorted(self._factories))


def register_sqlalchemy(registry: DatabaseRegistry) -> None:
    """Register the SQLAlchemy async backend."""
    registry.register("sqlalchemy", Database)


def default_database_registry() -> DatabaseRegistry:
    """Return a new registry containing the SQLAlchemy abstraction backend."""
    registry = DatabaseRegistry()
    register_sqlalchemy(registry)
    return registry
