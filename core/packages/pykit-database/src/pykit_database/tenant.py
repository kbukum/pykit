"""Multi-tenant database helpers for PostgreSQL RLS."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, text
from sqlalchemy.ext.asyncio import AsyncSession


async def set_session_variable(
    session: AsyncSession,
    name: str,
    value: str,
    *,
    is_local: bool = True,
) -> None:
    """Set a PostgreSQL session variable using ``set_config()``.

    When *is_local* is ``True`` the variable is scoped to the current
    transaction only.  This is used for PostgreSQL Row Level Security (RLS)
    policies that read session variables via ``current_setting()``.

    Args:
        session: The async SQLAlchemy session.
        name: The session variable name (e.g., ``"app.workspace_id"``).
        value: The value to set.
        is_local: If ``True``, scoped to current transaction only.

    Example:
        >>> async with db.session() as session:
        ...     await set_session_variable(session, "app.workspace_id", workspace_id)
    """
    await session.execute(
        text("SELECT set_config(:name, :value, :is_local)"),
        {"name": name, "value": value, "is_local": is_local},
    )


def scope_to_tenant(
    stmt: Select[Any],
    model_class: type[Any],
    column: str,
    value: Any,
) -> Select[Any]:
    """Add a tenant-scoping WHERE clause to a SQLAlchemy select statement.

    Args:
        stmt: The SQLAlchemy select statement to scope.
        model_class: The ORM model class.
        column: The column name to filter on (e.g., ``"workspace_id"``).
        value: The tenant ID value.

    Returns:
        The modified select statement with the WHERE clause applied.

    Example:
        >>> stmt = select(Content)
        >>> stmt = scope_to_tenant(stmt, Content, "workspace_id", ws_id)
    """
    return stmt.where(getattr(model_class, column) == value)
