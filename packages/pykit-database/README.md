# pykit-database

Async SQLAlchemy database toolkit with repository pattern, error translation, and component lifecycle.

## Installation

```bash
pip install pykit-database
# or
uv add pykit-database
```

## Quick Start

```python
from pykit_database import Database, DatabaseConfig, DatabaseComponent, Repository

# Direct usage
config = DatabaseConfig(dsn="sqlite+aiosqlite:///app.db", pool_size=5)
db = Database(config)

async with db.session() as session:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one()

# Repository pattern with full CRUD
repo = Repository(db.session, User)
user = await repo.create(User(name="Alice", email="alice@example.com"))
users = await repo.list(offset=0, limit=10, filters={"name": "Alice"})
await repo.delete(user.id)

# Component lifecycle integration
component = DatabaseComponent(config)
await component.start()     # connects and pings
health = await component.health()  # HEALTHY or UNHEALTHY
await component.stop()
```

## Key Components

- **DatabaseConfig** — Configuration dataclass with `dsn`, `echo`, `pool_size`, `max_overflow`, `pool_timeout`, `pool_recycle`, and `auto_migrate`
- **Database** — Async SQLAlchemy wrapper with `session()` context manager (auto-commit/rollback), `execute()`, `ping()`, `close()`, and `run_migrations(metadata)`
- **Repository[T]** — Generic CRUD repository with `create()`, `get_by_id()`, `list()`, `count()`, `exists()`, `update()`, `delete()`, and `save()` (upsert)
- **ReadRepository[T]** — Read-only repository with `get_by_id()`, `list()`, `count()`, and `exists()`
- **DatabaseComponent** — Component protocol implementation with `start()`, `stop()`, and `health()` for managed lifecycle
- **Error translation** — `translate_error()` maps SQLAlchemy exceptions to pykit `AppError` subtypes (NotFoundError, ServiceUnavailableError, ALREADY_EXISTS, DATABASE_ERROR)

## Dependencies

- `sqlalchemy[asyncio]` — Async SQLAlchemy ORM and core
- `pykit-errors` — Error types and translation
- `pykit-component` — Component lifecycle protocol

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
