# pykit-database

Async database abstraction with SQLAlchemy backend selection, explicit driver extras, repository
helpers, transaction rollback/cancellation behavior, tenant scoping, and component lifecycle.

## Installation

```bash
pip install pykit-database
pip install 'pykit-database[sqlite]'    # aiosqlite driver
pip install 'pykit-database[postgres]'  # asyncpg driver

uv add pykit-database
uv add 'pykit-database[sqlite]'    # aiosqlite driver
uv add 'pykit-database[postgres]'  # asyncpg driver
```

## Quick Start

```python
from pykit_database import Database, DatabaseConfig, Repository

db = Database(DatabaseConfig(dsn="sqlite+aiosqlite:///app.db"))

async with db.session() as session:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one()

repo = Repository(db.session, User)
created = await repo.create(User(name="Alice", email="alice@example.com"))
```

`Database.session()` commits on success and rolls back on exceptions and cancellation.

## Registry and component selection

```python
from pykit_database import (
    DatabaseComponent,
    DatabaseConfig,
    DatabaseRegistry,
    register_sqlalchemy,
)

registry = DatabaseRegistry()
register_sqlalchemy(registry)

component = DatabaseComponent(
    DatabaseConfig(backend="sqlalchemy", dsn="postgresql+asyncpg://..."),
    registry=registry,
)
await component.start()
```

## Tenant isolation

Use `scope_to_tenant()` to apply row-level tenant predicates and `set_session_variable()` for
PostgreSQL RLS session variables. Tenant IDs must be applied at repository/query boundaries.

## Key Components

- **DatabaseConfig** — backend, DSN, echo, and bounded pool settings.
- **DatabaseRegistry** — injected backend registry; empty registries have no backends.
- **Database** — SQLAlchemy async wrapper with sessions, execute, ping, close, migrations.
- **Repository[T]** / **ReadRepository[T]** — generic CRUD/read helpers.
- **tenant helpers** — row-scoped query filtering and PostgreSQL RLS variables.
