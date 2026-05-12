"""pykit_database — Async SQLAlchemy database toolkit with component lifecycle."""

from __future__ import annotations

from pykit_database.component import DatabaseComponent
from pykit_database.config import DatabaseConfig
from pykit_database.database import Database
from pykit_database.query import (
    PaginatedResult,
    Pagination,
    QueryConfig,
    QueryParams,
    apply_to_query,
    build_paginated_result,
    parse_query_params,
)
from pykit_database.registry import DatabaseRegistry, default_database_registry, register_sqlalchemy
from pykit_database.repository import ReadRepository, Repository
from pykit_database.tenant import scope_to_tenant, set_session_variable

__all__ = [
    "Database",
    "DatabaseComponent",
    "DatabaseConfig",
    "DatabaseRegistry",
    "PaginatedResult",
    "Pagination",
    "QueryConfig",
    "QueryParams",
    "ReadRepository",
    "Repository",
    "apply_to_query",
    "build_paginated_result",
    "default_database_registry",
    "parse_query_params",
    "register_sqlalchemy",
    "scope_to_tenant",
    "set_session_variable",
]
