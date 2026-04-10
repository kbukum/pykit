"""Extended tests for pykit-database – edge cases, concurrency, and isolation."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import Integer, String, select, text
from sqlalchemy.exc import IntegrityError, NoResultFound, OperationalError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from pykit_database.config import DatabaseConfig
from pykit_database.database import Database
from pykit_database.errors import (
    is_duplicate_error,
    translate_error,
)
from pykit_database.repository import Repository
from pykit_errors import AppError
from pykit_errors.codes import ErrorCode

# ---------------------------------------------------------------------------
# Test model (mirrors existing tests but scoped to this module)
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
    config = DatabaseConfig(dsn=IN_MEMORY_DSN)
    database = Database(config)
    await database.run_migrations(Base.metadata)
    yield database
    await database.close()


@pytest.fixture
async def repo(db: Database):
    return Repository(db.session, User)


# ---------------------------------------------------------------------------
# 1. Config validation edge cases
# ---------------------------------------------------------------------------


class TestConfigEdgeCases:
    def test_zero_pool_size(self):
        cfg = DatabaseConfig(pool_size=0)
        assert cfg.pool_size == 0

    def test_negative_max_overflow(self):
        cfg = DatabaseConfig(max_overflow=-1)
        assert cfg.max_overflow == -1

    def test_empty_dsn(self):
        cfg = DatabaseConfig(dsn="")
        assert cfg.dsn == ""

    def test_config_equality(self):
        cfg1 = DatabaseConfig(name="a", dsn=IN_MEMORY_DSN)
        cfg2 = DatabaseConfig(name="a", dsn=IN_MEMORY_DSN)
        assert cfg1 == cfg2

    def test_config_inequality(self):
        cfg1 = DatabaseConfig(name="a")
        cfg2 = DatabaseConfig(name="b")
        assert cfg1 != cfg2


# ---------------------------------------------------------------------------
# 2. Concurrent query execution
# ---------------------------------------------------------------------------


class TestConcurrentExecution:
    async def test_concurrent_reads_return_consistent_data(self, db: Database, repo: Repository):
        for i in range(5):
            await repo.create(User(name=f"User{i}", email=f"user{i}@x.com"))

        async def read_all():
            return await repo.list()

        results = await asyncio.gather(*[read_all() for _ in range(5)])
        for result in results:
            assert len(result) == 5

    async def test_concurrent_operations_dont_interfere(self, db: Database, repo: Repository):
        await repo.create(User(name="Seed", email="seed@x.com"))

        async def read_count():
            return await repo.count()

        async def read_exists():
            return await repo.exists(1)

        async def read_list():
            return await repo.list()

        count, exists, items = await asyncio.gather(read_count(), read_exists(), read_list())
        assert count == 1
        assert exists is True
        assert len(items) == 1

    async def test_concurrent_writes_unique_constraint(self, db: Database):
        async def insert_user(name: str, email: str):
            async with db.session() as sess:
                sess.add(User(name=name, email=email))

        # Concurrent inserts with different emails should all succeed
        await asyncio.gather(
            insert_user("A", "a@x.com"),
            insert_user("B", "b@x.com"),
            insert_user("C", "c@x.com"),
        )

        result = await db.execute(select(User))
        users = list(result.scalars().all())
        assert len(users) == 3


# ---------------------------------------------------------------------------
# 3. Transaction isolation
# ---------------------------------------------------------------------------


class TestTransactionIsolation:
    async def test_commit_makes_changes_visible(self, db: Database):
        async with db.session() as sess:
            sess.add(User(name="Committed", email="committed@x.com"))

        # After commit, the data should be visible in a new session
        async with db.session() as sess:
            result = await sess.execute(select(User).where(User.email == "committed@x.com"))
            user = result.scalars().first()
            assert user is not None
            assert user.name == "Committed"

    async def test_rollback_hides_changes(self, db: Database):
        with pytest.raises(ValueError, match="abort"):
            async with db.session() as sess:
                sess.add(User(name="Ghost", email="ghost@x.com"))
                await sess.flush()
                raise ValueError("abort")

        async with db.session() as sess:
            result = await sess.execute(select(User).where(User.email == "ghost@x.com"))
            assert result.scalars().first() is None

    async def test_nested_session_operations(self, db: Database):
        # First session creates a user
        async with db.session() as sess:
            sess.add(User(name="Outer", email="outer@x.com"))

        # Second session reads and creates another user
        async with db.session() as sess:
            result = await sess.execute(select(User).where(User.email == "outer@x.com"))
            outer = result.scalars().first()
            assert outer is not None
            sess.add(User(name="Inner", email="inner@x.com"))

        # Third session verifies both exist
        async with db.session() as sess:
            result = await sess.execute(select(User))
            users = result.scalars().all()
            assert len(users) == 2


# ---------------------------------------------------------------------------
# 4. Error mapping edge cases
# ---------------------------------------------------------------------------


class TestErrorEdgeCases:
    def test_is_duplicate_error_with_duplicate_keyword(self):
        exc = IntegrityError("", {}, Exception("duplicate entry for key"))
        assert is_duplicate_error(exc) is True

    def test_is_duplicate_error_no_keyword_returns_false(self):
        exc = IntegrityError("", {}, Exception("foreign key constraint failed"))
        assert is_duplicate_error(exc) is False

    def test_translate_error_empty_resource_uses_record(self):
        err = translate_error(NoResultFound(), "")
        assert "record" in str(err).lower()

    def test_translate_error_custom_resource_name(self):
        err = translate_error(NoResultFound(), "invoice")
        assert "invoice" in str(err).lower()

    def test_translate_connection_error_empty_resource(self):
        err = translate_error(OperationalError("", {}, Exception("timeout")), "")
        assert "database" in str(err).lower()

    def test_translate_duplicate_with_duplicate_keyword(self):
        exc = IntegrityError("", {}, Exception("duplicate entry"))
        err = translate_error(exc, "order")
        assert isinstance(err, AppError)
        assert err.code == ErrorCode.ALREADY_EXISTS
        assert "order" in str(err).lower()

    def test_translate_duplicate_empty_resource(self):
        exc = IntegrityError("", {}, Exception("UNIQUE constraint"))
        err = translate_error(exc, "")
        assert isinstance(err, AppError)
        assert "record" in str(err).lower()


# ---------------------------------------------------------------------------
# 5. Connection lifecycle
# ---------------------------------------------------------------------------


class TestConnectionLifecycle:
    async def test_close_then_new_operations(self):
        config = DatabaseConfig(dsn=IN_MEMORY_DSN)
        database = Database(config)
        await database.run_migrations(Base.metadata)

        async with database.session() as sess:
            sess.add(User(name="Pre", email="pre@x.com"))

        await database.close()

        # In-memory SQLite: after dispose, data is lost but engine still works
        # (a fresh connection is created transparently). Verify no crash.
        result = await database.execute(text("SELECT 1"))
        assert result.scalar() == 1
        await database.close()

    async def test_session_factory_creates_independent_sessions(self, db: Database):
        async with db.session() as s1:
            s1.add(User(name="S1", email="s1@x.com"))

        async with db.session() as s2:
            result = await s2.execute(select(User).where(User.email == "s1@x.com"))
            user = result.scalars().first()
            assert user is not None
            # Verify s2 is a different session object
            s2.add(User(name="S2", email="s2@x.com"))

        async with db.session() as s3:
            result = await s3.execute(select(User))
            assert len(result.scalars().all()) == 2

    async def test_multiple_sequential_sessions(self, db: Database):
        for i in range(3):
            async with db.session() as sess:
                sess.add(User(name=f"Seq{i}", email=f"seq{i}@x.com"))

        async with db.session() as sess:
            result = await sess.execute(select(User))
            assert len(result.scalars().all()) == 3


# ---------------------------------------------------------------------------
# 6. Repository edge cases
# ---------------------------------------------------------------------------


class TestRepositoryEdgeCases:
    async def test_list_offset_beyond_data_returns_empty(self, repo: Repository):
        await repo.create(User(name="A", email="a@x.com"))
        items = await repo.list(offset=100)
        assert items == []

    async def test_list_limit_zero_returns_empty(self, repo: Repository):
        await repo.create(User(name="A", email="a@x.com"))
        items = await repo.list(limit=0)
        assert items == []

    async def test_count_non_matching_filter_returns_zero(self, repo: Repository):
        await repo.create(User(name="Alice", email="alice@x.com"))
        count = await repo.count(filters={"name": "NonExistent"})
        assert count == 0

    async def test_exists_after_delete_returns_false(self, repo: Repository):
        user = await repo.create(User(name="Temp", email="temp@x.com"))
        uid = user.id
        assert await repo.exists(uid) is True
        await repo.delete(uid)
        assert await repo.exists(uid) is False
