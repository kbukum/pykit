"""Tests for validate_model() Pydantic integration."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from pykit_errors import InvalidInputError
from pykit_validation import validate_model


class _UserModel(BaseModel):
    name: str = Field(..., min_length=2)
    age: int = Field(..., ge=0)
    email: str


class TestValidateModel:
    def test_valid(self):
        user = validate_model(_UserModel, {"name": "Alice", "age": 30, "email": "a@b.com"})
        assert user.name == "Alice"
        assert user.age == 30

    def test_missing_fields(self):
        with pytest.raises(InvalidInputError) as exc_info:
            validate_model(_UserModel, {})
        err = exc_info.value
        assert "fields" in err.details
        assert len(err.details["fields"]) >= 1

    def test_invalid_values(self):
        with pytest.raises(InvalidInputError) as exc_info:
            validate_model(_UserModel, {"name": "A", "age": -1, "email": "x"})
        err = exc_info.value
        fields = {f["field"] for f in err.details["fields"]}
        assert "name" in fields
        assert "age" in fields

    def test_wrong_type(self):
        with pytest.raises(InvalidInputError):
            validate_model(_UserModel, {"name": "Alice", "age": "not_int", "email": "a@b.com"})

    def test_returns_model_instance(self):
        user = validate_model(_UserModel, {"name": "Bob", "age": 25, "email": "b@c.com"})
        assert isinstance(user, _UserModel)

    def test_extra_fields_ignored(self):
        user = validate_model(_UserModel, {"name": "Eve", "age": 20, "email": "e@f.com", "extra": "x"})
        assert user.name == "Eve"
