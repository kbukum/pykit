"""Async SQLAlchemy database wrapper."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from pykit_database.config import DatabaseConfig


class Database:
    """Thin wrapper around an async SQLAlchemy engine and session factory."""

    def __init__(self, config: DatabaseConfig) -> None:
        self._config = config

        # SQLite does not support pool_size / max_overflow / pool_timeout / pool_recycle
        is_sqlite = config.dsn.startswith("sqlite")
        engine_kwargs: dict[str, Any] = {
            "echo": config.echo,
        }
        if not is_sqlite:
            engine_kwargs.update(
                pool_size=config.pool_size,
                max_overflow=config.max_overflow,
                pool_timeout=config.pool_timeout,
                pool_recycle=config.pool_recycle,
            )

        self._engine: AsyncEngine = create_async_engine(config.dsn, **engine_kwargs)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    @property
    def engine(self) -> AsyncEngine:
        """Return the underlying async engine."""
        return self._engine

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield an ``AsyncSession`` that is committed on success and rolled back on error."""
        async with self._session_factory() as sess:
            try:
                yield sess
                await sess.commit()
            except BaseException:
                await sess.rollback()
                raise

    async def execute(self, stmt: Any) -> Any:
        """Execute a statement in a short-lived session and return the result."""
        async with self._session_factory() as sess:
            result = await sess.execute(stmt)
            await sess.commit()
            return result

    async def ping(self) -> bool:
        """Return ``True`` if the database is reachable."""
        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Dispose of the engine and release all pooled connections."""
        await self._engine.dispose()

    async def run_migrations(self, metadata: Any) -> None:
        """Create all tables defined in *metadata*."""
        async with self._engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
