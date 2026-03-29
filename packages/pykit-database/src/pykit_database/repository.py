"""Generic async repository pattern for SQLAlchemy models."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession


class ReadRepository[T]:
    """Read-only repository for SQLAlchemy ORM models."""

    def __init__(
        self,
        session_factory: Callable[..., AsyncIterator[AsyncSession]],
        model_class: type[T],
    ) -> None:
        self._session_factory = session_factory
        self._model_class = model_class

    # -- helpers --------------------------------------------------------------

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[AsyncSession]:
        async with self._session_factory() as sess:
            yield sess

    def _pk_column(self) -> Any:
        mapper = inspect(self._model_class)
        return mapper.primary_key[0]

    # -- queries --------------------------------------------------------------

    async def get_by_id(self, id: Any) -> T | None:
        """Return a single entity by primary key, or ``None``."""
        async with self._session() as sess:
            return await sess.get(self._model_class, id)

    async def list(
        self,
        offset: int = 0,
        limit: int = 100,
        filters: dict[str, Any] | None = None,
    ) -> list[T]:
        """Return a paginated list of entities, optionally filtered."""
        stmt = select(self._model_class)
        if filters:
            for col_name, value in filters.items():
                stmt = stmt.where(getattr(self._model_class, col_name) == value)
        stmt = stmt.offset(offset).limit(limit)

        async with self._session() as sess:
            result = await sess.execute(stmt)
            return list(result.scalars().all())

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        """Return the number of matching entities."""
        pk = self._pk_column()
        stmt = select(func.count(pk))
        if filters:
            for col_name, value in filters.items():
                stmt = stmt.where(getattr(self._model_class, col_name) == value)

        async with self._session() as sess:
            result = await sess.execute(stmt)
            return result.scalar_one()

    async def exists(self, id: Any) -> bool:
        """Return ``True`` if an entity with the given primary key exists."""
        return (await self.get_by_id(id)) is not None


class Repository[T](ReadRepository[T]):
    """Full CRUD repository extending :class:`ReadRepository`."""

    async def create(self, entity: T) -> T:
        """Persist a new entity and return it (with server-generated fields populated)."""
        async with self._session() as sess:
            sess.add(entity)
            await sess.flush()
            await sess.refresh(entity)
            return entity

    async def update(self, entity: T) -> T:
        """Merge changes for an existing entity and return the updated instance."""
        async with self._session() as sess:
            merged = await sess.merge(entity)
            await sess.flush()
            await sess.refresh(merged)
            return merged

    async def delete(self, id: Any) -> None:
        """Delete an entity by primary key. No-op if it does not exist."""
        async with self._session() as sess:
            entity = await sess.get(self._model_class, id)
            if entity is not None:
                await sess.delete(entity)

    async def save(self, entity: T) -> T:
        """Create or update (upsert-like): merge the entity into the session."""
        async with self._session() as sess:
            merged = await sess.merge(entity)
            await sess.flush()
            await sess.refresh(merged)
            return merged
