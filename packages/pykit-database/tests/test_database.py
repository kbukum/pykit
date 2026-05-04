"""Comprehensive tests for pykit-database using in-memory SQLite."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table
from sqlalchemy.exc import IntegrityError, NoResultFound, OperationalError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from pykit_component import HealthStatus
from pykit_database.component import DatabaseComponent
from pykit_database.config import DatabaseConfig
from pykit_database.database import Database
from pykit_database.errors import (
    is_connection_error,
    is_duplicate_error,
    is_not_found_error,
    translate_error,
)
from pykit_database.registry import DatabaseRegistry, default_database_registry, register_sqlalchemy
from pykit_database.repository import ReadRepository, Repository
from pykit_errors import AppError, NotFoundError, ServiceUnavailableError

# ---------------------------------------------------------------------------
# Test model
# ---------------------------------------------------------------------------

IN_MEMORY_DSN = "sqlite+aiosqlite://"


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def db():
    """Provide a Database connected to an in-memory SQLite."""
    config = DatabaseConfig(dsn=IN_MEMORY_DSN)
    database = Database(config)
    await database.run_migrations(Base.metadata)
    yield database
    await database.close()


@pytest.fixture
async def repo(db: Database):
    """Provide a Repository[User] backed by the in-memory database."""
    return Repository(db.session, User)


@pytest.fixture
async def read_repo(db: Database):
    """Provide a ReadRepository[User] backed by the in-memory database."""
    return ReadRepository(db.session, User)


# ---------------------------------------------------------------------------
# DatabaseConfig tests
# ---------------------------------------------------------------------------


class TestDatabaseConfig:
    def test_defaults(self):
        cfg = DatabaseConfig()
        assert cfg.name == "database"
        assert cfg.backend == "sqlalchemy"
        assert cfg.dsn == ""
        assert cfg.echo is False
        assert cfg.pool_size == 5
        assert cfg.max_overflow == 10
        assert cfg.pool_timeout == 30.0
        assert cfg.pool_recycle == 3600
        assert cfg.auto_migrate is False

    def test_empty_registry_has_no_side_effect_backends(self):
        registry = DatabaseRegistry()
        assert registry.names() == ()

    def test_explicit_sqlalchemy_registration(self):
        registry = DatabaseRegistry()
        register_sqlalchemy(registry)
        assert registry.names() == ("sqlalchemy",)

    def test_default_registry_contains_sqlalchemy(self):
        assert default_database_registry().names() == ("sqlalchemy",)

    def test_custom_values(self):
        cfg = DatabaseConfig(name="mydb", dsn="postgresql+asyncpg://localhost/test", echo=True)
        assert cfg.name == "mydb"
        assert cfg.dsn == "postgresql+asyncpg://localhost/test"
        assert cfg.echo is True


# ---------------------------------------------------------------------------
# Database tests
# ---------------------------------------------------------------------------


class TestDatabase:
    async def test_ping(self, db: Database):
        assert await db.ping() is True

    async def test_engine_property(self, db: Database):
        assert db.engine is not None

    async def test_session_yields_async_session(self, db: Database):
        async with db.session() as sess:
            assert sess is not None

    async def test_execute(self, db: Database):
        from sqlalchemy import text

        result = await db.execute(text("SELECT 1"))
        row = result.scalar()
        assert row == 1

    async def test_close_disposes_engine(self):
        config = DatabaseConfig(dsn=IN_MEMORY_DSN)
        database = Database(config)
        assert await database.ping() is True
        await database.close()
        # After dispose, the pool is invalidated; for in-memory SQLite a new
        # connection is transparently created, so we just verify close() doesn't raise.

    async def test_session_rollback_on_error(self):
        """Cover database.py lines 48-50: session rollback on exception."""
        config = DatabaseConfig(dsn=IN_MEMORY_DSN)
        database = Database(config)
        await database.run_migrations(Base.metadata)

        with pytest.raises(RuntimeError, match="forced"):
            async with database.session() as sess:
                sess.add(User(name="Ghost", email="ghost@x.com"))
                raise RuntimeError("forced")

        # The insert should have been rolled back
        from sqlalchemy import select

        async with database.session() as sess:
            result = await sess.execute(select(User).where(User.email == "ghost@x.com"))
            assert result.scalars().first() is None
        await database.close()

    async def test_session_rollback_on_cancellation(self):
        config = DatabaseConfig(dsn=IN_MEMORY_DSN)
        database = Database(config)
        await database.run_migrations(Base.metadata)

        async def insert_then_cancel() -> None:
            async with database.session() as sess:
                sess.add(User(name="Cancelled", email="cancelled@x.com"))
                await sess.flush()
                raise asyncio.CancelledError

        with pytest.raises(asyncio.CancelledError):
            await insert_then_cancel()

        from sqlalchemy import select

        async with database.session() as sess:
            result = await sess.execute(select(User).where(User.email == "cancelled@x.com"))
            assert result.scalars().first() is None
        await database.close()

    async def test_session_rollback_is_shielded(self):
        config = DatabaseConfig(dsn=IN_MEMORY_DSN)
        database = Database(config)
        await database.run_migrations(Base.metadata)

        original_shield = asyncio.shield
        shielded = False

        async def shield_spy(awaitable):
            nonlocal shielded
            shielded = True
            return await original_shield(awaitable)

        from unittest.mock import patch as _patch

        with (
            _patch("pykit_database.database.asyncio.shield", side_effect=shield_spy),
            pytest.raises(RuntimeError, match="forced rollback"),
        ):
            async with database.session() as sess:
                sess.add(User(name="Shielded", email="shielded@x.com"))
                await sess.flush()
                raise RuntimeError("forced rollback")

        assert shielded is True
        await database.close()

    async def test_ping_returns_false_on_failure(self):
        """Cover database.py lines 65-66: ping returns False when exception occurs."""
        config = DatabaseConfig(dsn=IN_MEMORY_DSN)
        database = Database(config)
        # Dispose engine so pool connections are gone, then replace engine
        await database.close()

        # Create a new engine that will always fail to connect
        from unittest.mock import patch as _patch

        with _patch("pykit_database.database.create_async_engine") as mock_create:
            bad_engine = mock_create.return_value
            bad_engine.connect.side_effect = Exception("dead")
            bad_db = Database(config)
            bad_db._engine = bad_engine
            result = await bad_db.ping()
        assert result is False

    async def test_non_sqlite_config_uses_pool_args(self):
        """Cover database.py line 26: non-SQLite DSN includes pool kwargs."""
        from unittest.mock import patch as _patch

        with _patch("pykit_database.database.create_async_engine") as mock_create:
            config = DatabaseConfig(dsn="postgresql+asyncpg://user:pass@localhost/testdb")
            Database(config)  # constructor is all we need to exercise
            call_kwargs = mock_create.call_args[1]
            assert "pool_size" in call_kwargs
            assert "max_overflow" in call_kwargs
            assert "pool_timeout" in call_kwargs
            assert "pool_recycle" in call_kwargs

    async def test_run_migrations_creates_tables(self):
        config = DatabaseConfig(dsn=IN_MEMORY_DSN)
        database = Database(config)

        metadata = MetaData()
        Table("test_table", metadata, Column("id", Integer, primary_key=True), Column("value", String(50)))

        await database.run_migrations(metadata)

        from sqlalchemy import text

        result = await database.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = [row[0] for row in result.fetchall()]
        assert "test_table" in tables
        await database.close()


# ---------------------------------------------------------------------------
# Repository CRUD tests
# ---------------------------------------------------------------------------


class TestRepository:
    async def test_create_and_get_by_id(self, repo: Repository):
        user = User(name="Alice", email="alice@example.com")
        created = await repo.create(user)

        assert created.id is not None
        fetched = await repo.get_by_id(created.id)
        assert fetched is not None
        assert fetched.name == "Alice"

    async def test_get_by_id_missing(self, repo: Repository):
        result = await repo.get_by_id(9999)
        assert result is None

    async def test_list_empty(self, repo: Repository):
        items = await repo.list()
        assert items == []

    async def test_list_with_items(self, repo: Repository):
        await repo.create(User(name="A", email="a@x.com"))
        await repo.create(User(name="B", email="b@x.com"))

        items = await repo.list()
        assert len(items) == 2

    async def test_list_pagination(self, repo: Repository):
        for i in range(5):
            await repo.create(User(name=f"User{i}", email=f"u{i}@x.com"))

        page = await repo.list(offset=2, limit=2)
        assert len(page) == 2

    async def test_list_with_filters(self, repo: Repository):
        await repo.create(User(name="Alice", email="alice@x.com"))
        await repo.create(User(name="Bob", email="bob@x.com"))

        items = await repo.list(filters={"name": "Alice"})
        assert len(items) == 1
        assert items[0].name == "Alice"

    async def test_count(self, repo: Repository):
        assert await repo.count() == 0
        await repo.create(User(name="A", email="a@x.com"))
        assert await repo.count() == 1

    async def test_count_with_filters(self, repo: Repository):
        await repo.create(User(name="Alice", email="alice@x.com"))
        await repo.create(User(name="Bob", email="bob@x.com"))

        assert await repo.count(filters={"name": "Alice"}) == 1

    async def test_exists(self, repo: Repository):
        user = await repo.create(User(name="A", email="a@x.com"))
        assert await repo.exists(user.id) is True
        assert await repo.exists(9999) is False

    async def test_update(self, repo: Repository):
        user = await repo.create(User(name="Old", email="u@x.com"))
        user.name = "New"
        updated = await repo.update(user)
        assert updated.name == "New"

        fetched = await repo.get_by_id(user.id)
        assert fetched is not None
        assert fetched.name == "New"

    async def test_delete(self, repo: Repository):
        user = await repo.create(User(name="A", email="a@x.com"))
        uid = user.id
        await repo.delete(uid)
        assert await repo.get_by_id(uid) is None

    async def test_delete_missing(self, repo: Repository):
        # Should not raise
        await repo.delete(9999)

    async def test_save_creates_new(self, repo: Repository):
        user = User(id=42, name="New", email="new@x.com")
        saved = await repo.save(user)
        assert saved.id == 42

        fetched = await repo.get_by_id(42)
        assert fetched is not None
        assert fetched.name == "New"

    async def test_save_updates_existing(self, repo: Repository):
        user = await repo.create(User(name="Old", email="old@x.com"))
        user.name = "Updated"
        saved = await repo.save(user)
        assert saved.name == "Updated"


class TestReadRepository:
    async def test_read_only_operations(self, db: Database, read_repo: ReadRepository):
        # Seed data via direct session
        async with db.session() as sess:
            sess.add(User(name="Reader", email="reader@x.com"))

        items = await read_repo.list()
        assert len(items) == 1
        assert items[0].name == "Reader"

        assert await read_repo.count() == 1
        assert await read_repo.exists(items[0].id) is True


# ---------------------------------------------------------------------------
# Error translation tests
# ---------------------------------------------------------------------------


class TestErrors:
    def test_is_connection_error(self):
        assert is_connection_error(OperationalError("", {}, Exception())) is True
        assert is_connection_error(ValueError()) is False

    def test_is_not_found_error(self):
        assert is_not_found_error(NoResultFound()) is True
        assert is_not_found_error(ValueError()) is False

    def test_is_duplicate_error(self):
        exc = IntegrityError("", {}, Exception("UNIQUE constraint failed"))
        assert is_duplicate_error(exc) is True
        assert is_duplicate_error(ValueError()) is False

    def test_translate_not_found(self):
        err = translate_error(NoResultFound(), "user")
        assert isinstance(err, NotFoundError)
        assert "user" in str(err)

    def test_translate_connection_error(self):
        err = translate_error(OperationalError("", {}, Exception("conn refused")), "db")
        assert isinstance(err, ServiceUnavailableError)

    def test_translate_duplicate_error(self):
        exc = IntegrityError("", {}, Exception("UNIQUE constraint failed"))
        err = translate_error(exc, "user")
        assert isinstance(err, AppError)
        assert "duplicate" in str(err)

    def test_translate_unknown_error(self):
        err = translate_error(RuntimeError("boom"))
        assert isinstance(err, AppError)
        assert "boom" in str(err)


# ---------------------------------------------------------------------------
# Component lifecycle tests
# ---------------------------------------------------------------------------


class TestDatabaseComponent:
    async def test_start_and_stop(self):
        cfg = DatabaseConfig(dsn=IN_MEMORY_DSN)
        comp = DatabaseComponent(cfg)

        assert comp.database is None
        await comp.start()
        assert comp.database is not None
        await comp.stop()
        assert comp.database is None

    async def test_name(self):
        comp = DatabaseComponent(DatabaseConfig(name="mydb"))
        assert comp.name == "mydb"

    async def test_health_before_start(self):
        comp = DatabaseComponent(DatabaseConfig())
        h = await comp.health()
        assert h.status == HealthStatus.UNHEALTHY
        assert "not started" in h.message

    async def test_health_after_start(self):
        comp = DatabaseComponent(DatabaseConfig(dsn=IN_MEMORY_DSN))
        await comp.start()

        h = await comp.health()
        assert h.status == HealthStatus.HEALTHY

        await comp.stop()

    async def test_double_stop_is_safe(self):
        comp = DatabaseComponent(DatabaseConfig(dsn=IN_MEMORY_DSN))
        await comp.start()
        await comp.stop()
        await comp.stop()  # should not raise

    async def test_health_ping_fails(self):
        """Cover component.py line 40: ping returns False → UNHEALTHY."""
        comp = DatabaseComponent(DatabaseConfig(dsn=IN_MEMORY_DSN))
        await comp.start()
        # Monkey-patch ping to return False
        comp._database.ping = AsyncMock(return_value=False)
        h = await comp.health()
        assert h.status == HealthStatus.UNHEALTHY
        assert "ping failed" in h.message
        await comp.stop()

    async def test_start_unreachable_raises(self):
        """Cover component.py line 26: start raises when ping returns False."""
        from unittest.mock import patch as _patch

        cfg = DatabaseConfig(dsn=IN_MEMORY_DSN, name="unreachable")
        comp = DatabaseComponent(cfg)
        with (
            _patch.object(Database, "ping", return_value=False),
            pytest.raises(RuntimeError, match="not reachable"),
        ):
            await comp.start()
