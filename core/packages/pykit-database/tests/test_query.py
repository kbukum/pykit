"""Tests for query parameter parsing and pagination helpers."""

from sqlalchemy import Column, DateTime, Integer, String, func, select
from sqlalchemy.orm import DeclarativeBase

from pykit_database.query import (
    PaginatedResult,
    QueryConfig,
    QueryParams,
    apply_to_query,
    build_paginated_result,
    parse_query_params,
)

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    status = Column(String)
    category = Column(String)
    created_at = Column(DateTime, server_default=func.now())


def _compile(stmt) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))


# ---------------------------------------------------------------------------
# parse_query_params
# ---------------------------------------------------------------------------


def test_parse_defaults() -> None:
    params = parse_query_params({})
    assert params.page == 1
    assert params.page_size == 20
    assert params.sort_by == "created_at"
    assert params.sort_order == "desc"
    assert params.filters == {}
    assert params.search is None


def test_parse_page_aliases() -> None:
    assert parse_query_params({"page_size": "15"}).page_size == 15
    assert parse_query_params({"per_page": "25"}).page_size == 25
    assert parse_query_params({"pageSize": "30"}).page_size == 30


def test_parse_sort_aliases() -> None:
    assert parse_query_params({"sort_by": "name"}).sort_by == "name"
    assert parse_query_params({"sort": "name"}).sort_by == "name"
    assert parse_query_params({"sortBy": "name"}).sort_by == "name"
    assert parse_query_params({"order_by": "name"}).sort_by == "name"


def test_parse_sort_order_aliases() -> None:
    assert parse_query_params({"sort_order": "asc"}).sort_order == "asc"
    assert parse_query_params({"order": "asc"}).sort_order == "asc"
    assert parse_query_params({"sortOrder": "asc"}).sort_order == "asc"
    assert parse_query_params({"direction": "asc"}).sort_order == "asc"


def test_parse_search_aliases() -> None:
    assert parse_query_params({"search": "hello"}).search == "hello"
    assert parse_query_params({"q": "hello"}).search == "hello"
    assert parse_query_params({"query": "hello"}).search == "hello"


def test_parse_clamps_page_size() -> None:
    cfg = QueryConfig(max_page_size=50, default_page_size=10)
    assert parse_query_params({"page_size": "999"}, cfg).page_size == 50
    assert parse_query_params({"page_size": "0"}, cfg).page_size == 10
    assert parse_query_params({"page_size": "-5"}, cfg).page_size == 10


def test_parse_validates_sort_fields() -> None:
    cfg = QueryConfig(allowed_sort_fields=frozenset({"name", "created_at"}))
    assert parse_query_params({"sort_by": "name"}, cfg).sort_by == "name"
    assert parse_query_params({"sort_by": "unknown"}, cfg).sort_by == "created_at"


def test_parse_invalid_sort_order_falls_back() -> None:
    params = parse_query_params({"sort_order": "random"})
    assert params.sort_order == "desc"


def test_parse_invalid_page_falls_back() -> None:
    params = parse_query_params({"page": "-1"})
    assert params.page == 1

    params2 = parse_query_params({"page": "abc"})
    assert params2.page == 1


def test_parse_filters() -> None:
    cfg = QueryConfig(allowed_filter_fields=frozenset({"status", "category"}))
    params = parse_query_params({"status": "active", "category": "A", "unknown": "x"}, cfg)
    assert params.filters == {"status": "active", "category": "A"}


def test_parse_filters_empty_when_none_allowed() -> None:
    params = parse_query_params({"status": "active"})
    assert params.filters == {}


# ---------------------------------------------------------------------------
# QueryParams.offset
# ---------------------------------------------------------------------------


def test_query_params_offset() -> None:
    assert QueryParams(page=1, page_size=20).offset == 0
    assert QueryParams(page=2, page_size=20).offset == 20
    assert QueryParams(page=3, page_size=10).offset == 20
    assert QueryParams(page=5, page_size=25).offset == 100


# ---------------------------------------------------------------------------
# apply_to_query
# ---------------------------------------------------------------------------


def test_apply_to_query_pagination() -> None:
    stmt = select(Item)
    params = QueryParams(page=3, page_size=10)
    result = apply_to_query(stmt, params, Item)
    compiled = _compile(result)
    assert "LIMIT 10" in compiled
    assert "OFFSET 20" in compiled


def test_apply_to_query_sorting_desc() -> None:
    stmt = select(Item)
    params = QueryParams(sort_by="name", sort_order="desc")
    compiled = _compile(apply_to_query(stmt, params, Item))
    assert "name DESC" in compiled


def test_apply_to_query_sorting_asc() -> None:
    stmt = select(Item)
    params = QueryParams(sort_by="name", sort_order="asc")
    compiled = _compile(apply_to_query(stmt, params, Item))
    assert "name ASC" in compiled


def test_apply_to_query_filters() -> None:
    stmt = select(Item)
    params = QueryParams(filters={"status": "active"})
    compiled = _compile(apply_to_query(stmt, params, Item))
    assert "status" in compiled
    assert "active" in compiled


def test_apply_to_query_skips_unknown_columns() -> None:
    stmt = select(Item)
    params = QueryParams(sort_by="nonexistent", filters={"bogus": "val"})
    compiled = _compile(apply_to_query(stmt, params, Item))
    assert "nonexistent" not in compiled
    assert "bogus" not in compiled


# ---------------------------------------------------------------------------
# build_paginated_result
# ---------------------------------------------------------------------------


def test_build_paginated_result() -> None:
    params = QueryParams(page=2, page_size=10)
    result = build_paginated_result(["a", "b", "c"], total=25, params=params)

    assert isinstance(result, PaginatedResult)
    assert result.data == ["a", "b", "c"]
    assert result.pagination.page == 2
    assert result.pagination.page_size == 10
    assert result.pagination.total == 25
    assert result.pagination.total_pages == 3


def test_build_paginated_result_empty() -> None:
    params = QueryParams(page=1, page_size=20)
    result = build_paginated_result([], total=0, params=params)

    assert result.data == []
    assert result.pagination.total == 0
    assert result.pagination.total_pages == 1


def test_build_paginated_result_exact_pages() -> None:
    params = QueryParams(page=1, page_size=10)
    result = build_paginated_result(list(range(10)), total=30, params=params)
    assert result.pagination.total_pages == 3


def test_build_paginated_result_partial_last_page() -> None:
    params = QueryParams(page=1, page_size=10)
    result = build_paginated_result(list(range(10)), total=31, params=params)
    assert result.pagination.total_pages == 4
