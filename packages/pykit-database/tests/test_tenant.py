"""Tests for multi-tenant database helpers."""

from sqlalchemy import Column, Integer, String, select
from sqlalchemy.orm import DeclarativeBase

from pykit_database.tenant import scope_to_tenant, set_session_variable


class Base(DeclarativeBase):
    pass


class FakeModel(Base):
    __tablename__ = "fake"
    id = Column(Integer, primary_key=True)
    workspace_id = Column(String)
    name = Column(String)


def test_scope_to_tenant_adds_where_clause() -> None:
    stmt = select(FakeModel)
    scoped = scope_to_tenant(stmt, FakeModel, "workspace_id", "ws-123")
    compiled = str(scoped.compile(compile_kwargs={"literal_binds": True}))
    assert "workspace_id" in compiled
    assert "ws-123" in compiled


def test_scope_to_tenant_preserves_existing_where() -> None:
    stmt = select(FakeModel).where(FakeModel.name == "test")
    scoped = scope_to_tenant(stmt, FakeModel, "workspace_id", "ws-456")
    compiled = str(scoped.compile(compile_kwargs={"literal_binds": True}))
    assert "workspace_id" in compiled
    assert "ws-456" in compiled
    assert "name" in compiled


def test_set_session_variable_is_importable() -> None:
    """Verify set_session_variable is importable and callable."""
    assert callable(set_session_variable)
