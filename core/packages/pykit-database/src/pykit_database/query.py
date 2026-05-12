"""Query parameter parsing and pagination helpers for SQLAlchemy."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Select, asc, desc


@dataclass(frozen=True)
class QueryConfig:
    """Configuration for query parameter parsing and validation.

    Attributes:
        default_page_size: Default number of results per page.
        max_page_size: Maximum allowed page size.
        allowed_sort_fields: Set of column names allowed for sorting.
        allowed_filter_fields: Set of column names allowed for filtering.
        default_sort_field: Default sort column if none specified.
        default_sort_order: Default sort direction ("asc" or "desc").
    """

    default_page_size: int = 20
    max_page_size: int = 100
    allowed_sort_fields: frozenset[str] = field(default_factory=frozenset)
    allowed_filter_fields: frozenset[str] = field(default_factory=frozenset)
    default_sort_field: str = "created_at"
    default_sort_order: str = "desc"


@dataclass(frozen=True)
class QueryParams:
    """Parsed and validated query parameters.

    Attributes:
        page: Current page number (1-indexed).
        page_size: Number of results per page.
        sort_by: Column name to sort by.
        sort_order: Sort direction ("asc" or "desc").
        filters: Dict of column -> value filters.
        search: Optional search query string.
    """

    page: int = 1
    page_size: int = 20
    sort_by: str = "created_at"
    sort_order: str = "desc"
    filters: dict[str, Any] = field(default_factory=dict)
    search: str | None = None

    @property
    def offset(self) -> int:
        """Calculate the SQL offset from page and page_size."""
        return (self.page - 1) * self.page_size


@dataclass(frozen=True)
class Pagination:
    """Pagination metadata.

    Attributes:
        page: Current page number.
        page_size: Results per page.
        total: Total number of results.
        total_pages: Total number of pages.
    """

    page: int
    page_size: int
    total: int
    total_pages: int


@dataclass(frozen=True)
class PaginatedResult[T]:
    """A page of results with pagination metadata.

    Attributes:
        data: The list of results for this page.
        pagination: Pagination metadata.
    """

    data: list[T]
    pagination: Pagination


def parse_query_params(
    query_dict: dict[str, str],
    config: QueryConfig | None = None,
) -> QueryParams:
    """Parse and validate query parameters from a request.

    Handles common parameter name aliases:
    - page: ``"page"``
    - page_size: ``"page_size"``, ``"per_page"``, ``"pageSize"``
    - sort_by: ``"sort_by"``, ``"sort"``, ``"sortBy"``, ``"order_by"``
    - sort_order: ``"sort_order"``, ``"order"``, ``"sortOrder"``, ``"direction"``
    - search: ``"search"``, ``"q"``, ``"query"``
    - All other allowed filter fields are extracted as filters.

    Args:
        query_dict: Dictionary of query string parameters.
        config: Optional query configuration for defaults and validation.

    Returns:
        Validated ``QueryParams``.
    """
    cfg = config or QueryConfig()

    page = _parse_int(query_dict.get("page"), default=1)
    page = max(page, 1)

    raw_size = query_dict.get("page_size") or query_dict.get("per_page") or query_dict.get("pageSize")
    page_size = _parse_int(raw_size, default=cfg.default_page_size)
    if page_size < 1:
        page_size = cfg.default_page_size
    page_size = min(page_size, cfg.max_page_size)

    sort_by = (
        query_dict.get("sort_by")
        or query_dict.get("sort")
        or query_dict.get("sortBy")
        or query_dict.get("order_by")
        or cfg.default_sort_field
    )
    if cfg.allowed_sort_fields and sort_by not in cfg.allowed_sort_fields:
        sort_by = cfg.default_sort_field

    sort_order = (
        query_dict.get("sort_order")
        or query_dict.get("order")
        or query_dict.get("sortOrder")
        or query_dict.get("direction")
        or cfg.default_sort_order
    )
    if sort_order not in ("asc", "desc"):
        sort_order = cfg.default_sort_order

    search = query_dict.get("search") or query_dict.get("q") or query_dict.get("query") or None

    filters: dict[str, Any] = {}
    if cfg.allowed_filter_fields:
        for filter_field in cfg.allowed_filter_fields:
            if filter_field in query_dict:
                filters[filter_field] = query_dict[filter_field]

    return QueryParams(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        filters=filters,
        search=search,
    )


def apply_to_query(
    stmt: Select[Any],
    params: QueryParams,
    model_class: type[Any],
) -> Select[Any]:
    """Apply QueryParams (sorting, filtering, pagination) to a SQLAlchemy Select.

    Args:
        stmt: The base SQLAlchemy select statement.
        params: Parsed query parameters.
        model_class: The ORM model class for column references.

    Returns:
        Modified select statement with sorting, filtering, and pagination applied.
    """
    for col_name, value in params.filters.items():
        if hasattr(model_class, col_name):
            stmt = stmt.where(getattr(model_class, col_name) == value)

    if hasattr(model_class, params.sort_by):
        col = getattr(model_class, params.sort_by)
        stmt = stmt.order_by(desc(col) if params.sort_order == "desc" else asc(col))

    stmt = stmt.offset(params.offset).limit(params.page_size)

    return stmt


def build_paginated_result[T](
    data: list[T],
    total: int,
    params: QueryParams,
) -> PaginatedResult[T]:
    """Build a PaginatedResult from data, total count, and query params.

    Args:
        data: The list of results for the current page.
        total: Total number of matching results.
        params: The query parameters used.

    Returns:
        ``PaginatedResult`` with data and pagination metadata.
    """
    total_pages = max(1, math.ceil(total / params.page_size))
    return PaginatedResult(
        data=data,
        pagination=Pagination(
            page=params.page,
            page_size=params.page_size,
            total=total,
            total_pages=total_pages,
        ),
    )


def _parse_int(value: str | None, *, default: int) -> int:
    """Parse a string as int, returning *default* on failure."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default
