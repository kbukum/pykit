"""Database configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DatabaseConfig:
    """Configuration for async SQLAlchemy database connections."""

    name: str = "database"
    backend: str = "sqlalchemy"
    dsn: str = "sqlite+aiosqlite:///db.sqlite3"
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: float = 30.0
    pool_recycle: int = 3600
    auto_migrate: bool = False
