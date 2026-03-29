"""Database component with lifecycle management."""

from __future__ import annotations

from pykit_component import Component, Health, HealthStatus
from pykit_database.config import DatabaseConfig
from pykit_database.database import Database


class DatabaseComponent:
    """Wraps :class:`Database` with :class:`Component` lifecycle semantics."""

    def __init__(self, config: DatabaseConfig) -> None:
        self._config = config
        self._database: Database | None = None

    # -- Component protocol --------------------------------------------------

    @property
    def name(self) -> str:
        return self._config.name

    async def start(self) -> None:
        self._database = Database(self._config)
        if not await self._database.ping():
            raise RuntimeError(f"database '{self._config.name}' is not reachable")

    async def stop(self) -> None:
        if self._database is not None:
            await self._database.close()
            self._database = None

    async def health(self) -> Health:
        if self._database is None:
            return Health(name=self.name, status=HealthStatus.UNHEALTHY, message="not started")

        ok = await self._database.ping()
        if ok:
            return Health(name=self.name, status=HealthStatus.HEALTHY)
        return Health(name=self.name, status=HealthStatus.UNHEALTHY, message="ping failed")

    # -- Accessor -------------------------------------------------------------

    @property
    def database(self) -> Database | None:
        """Return the underlying :class:`Database`, or ``None`` before :meth:`start`."""
        return self._database


# Ensure the class satisfies the Component protocol at import time.
_: type[Component] = DatabaseComponent  # type: ignore[assignment]
