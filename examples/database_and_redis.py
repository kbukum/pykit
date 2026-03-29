"""Example: Database repository pattern and Redis typed store.

Demonstrates:
- Async SQLite database with the Repository pattern
- TypedStore with key prefixes for Redis
- Both wrapped in asyncio.run

NOTE: The database example uses an in-memory SQLite via aiosqlite.
NOTE: The Redis example requires a running Redis server (redis://localhost:6379).
"""

from __future__ import annotations

import asyncio

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import DeclarativeBase

from pykit_database import Database, DatabaseConfig, Repository

# ---------------------------------------------------------------------------
# 1. Database — async SQLite with Repository
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(200), nullable=False)


async def demo_database() -> None:
    """CRUD via Repository backed by an in-memory SQLite database."""
    print("=== Database Repository ===")

    db = Database(DatabaseConfig(dsn="sqlite+aiosqlite://", echo=False))

    # Create tables
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    repo: Repository[User] = Repository(db.session, User)

    # Create
    alice = await repo.create(User(name="Alice", email="alice@example.com"))
    bob = await repo.create(User(name="Bob", email="bob@example.com"))
    print(f"  Created: {alice.name} (id={alice.id}), {bob.name} (id={bob.id})")

    # Read
    found = await repo.get_by_id(alice.id)
    print(f"  Found by id: {found.name if found else 'N/A'}")

    # List
    users = await repo.list(limit=10)
    print(f"  All users: {[u.name for u in users]}")

    # Count
    total = await repo.count()
    print(f"  Total count: {total}")

    # Update
    if found:
        found.email = "alice@newdomain.com"
        updated = await repo.update(found)
        print(f"  Updated email: {updated.email}")

    # Delete
    await repo.delete(bob.id)
    remaining = await repo.list()
    print(f"  After delete: {[u.name for u in remaining]}")

    await db.close()
    print("  Database closed.")


# ---------------------------------------------------------------------------
# 2. Redis — TypedStore with key prefixes
# ---------------------------------------------------------------------------


async def demo_redis() -> None:
    """Show TypedStore usage with a Redis backend.

    NOTE: requires a running Redis server at localhost:6379.
    """
    from pykit_redis import RedisClient, RedisConfig, TypedStore

    print("\n=== Redis TypedStore ===")
    print("  NOTE: requires running Redis at localhost:6379")

    config = RedisConfig(url="redis://localhost:6379/0")
    client = RedisClient(config)

    # TypedStore automatically prefixes keys and handles JSON serialization
    store: TypedStore[dict] = TypedStore(client, key_prefix="myapp:users")

    try:
        await store.save("1", {"name": "Alice", "role": "admin"}, ttl=300)
        await store.save("2", {"name": "Bob", "role": "viewer"}, ttl=300)

        user = await store.load("1")
        print(f"  Loaded user 1: {user}")

        await store.delete("2")
        gone = await store.load("2")
        print(f"  After delete user 2: {gone}")
    except Exception as exc:
        print(f"  Redis unavailable (expected in demo): {type(exc).__name__}: {exc}")
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    await demo_database()
    await demo_redis()


if __name__ == "__main__":
    asyncio.run(main())
