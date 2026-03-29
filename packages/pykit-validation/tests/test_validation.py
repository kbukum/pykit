"""Comprehensive tests for pykit_validation."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from pykit_errors import InvalidInputError
from pykit_validation import FieldError, Validator, validate_model

# ---------------------------------------------------------------------------
# Validator — individual checks
# ---------------------------------------------------------------------------


class TestRequired:
    def test_empty_string(self):
        v = Validator().required("name", "")
        assert v.has_errors
        assert v.errors[0] == FieldError(field="name", message="is required")

    def test_whitespace_only(self):
        v = Validator().required("name", "   ")
        assert v.has_errors

    def test_valid(self):
        v = Validator().required("name", "Alice")
        assert not v.has_errors


class TestMaxLength:
    def test_exceeds(self):
        v = Validator().max_length("bio", "a" * 11, 10)
        assert v.has_errors
        assert "10 characters or less" in v.errors[0].message

    def test_within(self):
        v = Validator().max_length("bio", "hello", 10)
        assert not v.has_errors

    def test_exact_boundary(self):
        v = Validator().max_length("bio", "a" * 10, 10)
        assert not v.has_errors


class TestMinLength:
    def test_too_short(self):
        v = Validator().min_length("password", "ab", 8)
        assert v.has_errors
        assert "at least 8 characters" in v.errors[0].message

    def test_valid(self):
        v = Validator().min_length("password", "abcdefgh", 8)
        assert not v.has_errors


class TestRangeCheck:
    def test_below(self):
        v = Validator().range_check("age", 5, 18, 120)
        assert v.has_errors
        assert "between 18 and 120" in v.errors[0].message

    def test_above(self):
        v = Validator().range_check("age", 200, 18, 120)
        assert v.has_errors

    def test_within(self):
        v = Validator().range_check("age", 25, 18, 120)
        assert not v.has_errors

    def test_boundary(self):
        v = Validator().range_check("age", 18, 18, 120)
        assert not v.has_errors


class TestMinValue:
    def test_below(self):
        v = Validator().min_value("score", 3, 5)
        assert v.has_errors
        assert "at least 5" in v.errors[0].message

    def test_valid(self):
        v = Validator().min_value("score", 10, 5)
        assert not v.has_errors


class TestMaxValue:
    def test_exceeds(self):
        v = Validator().max_value("score", 101, 100)
        assert v.has_errors
        assert "100 or less" in v.errors[0].message

    def test_valid(self):
        v = Validator().max_value("score", 99, 100)
        assert not v.has_errors


class TestPattern:
    def test_no_match(self):
        v = Validator().pattern("email", "not-an-email", r"^[\w.+-]+@[\w-]+\.[\w.]+$")
        assert v.has_errors
        assert "does not match required format" in v.errors[0].message

    def test_match(self):
        v = Validator().pattern("email", "a@b.com", r"^[\w.+-]+@[\w-]+\.[\w.]+$")
        assert not v.has_errors

    def test_empty_skipped(self):
        v = Validator().pattern("email", "", r"^.+@.+$")
        assert not v.has_errors


class TestOneOf:
    def test_invalid(self):
        v = Validator().one_of("role", "superadmin", ["admin", "user", "editor"])
        assert v.has_errors
        assert "must be one of: admin, user, editor" in v.errors[0].message

    def test_valid(self):
        v = Validator().one_of("role", "admin", ["admin", "user", "editor"])
        assert not v.has_errors

    def test_empty_skipped(self):
        v = Validator().one_of("role", "", ["admin", "user"])
        assert not v.has_errors


class TestCustom:
    def test_false_condition(self):
        v = Validator().custom(False, "password", "must contain a digit")
        assert v.has_errors
        assert v.errors[0].message == "must contain a digit"

    def test_true_condition(self):
        v = Validator().custom(True, "password", "must contain a digit")
        assert not v.has_errors


# ---------------------------------------------------------------------------
# Chaining & error accumulation
# ---------------------------------------------------------------------------


class TestChaining:
    def test_multiple_errors(self):
        v = (
            Validator()
            .required("name", "")
            .min_length("password", "ab", 8)
            .one_of("role", "x", ["admin", "user"])
        )
        assert len(v.errors) == 3
        assert v.errors[0].field == "name"
        assert v.errors[1].field == "password"
        assert v.errors[2].field == "role"

    def test_no_errors(self):
        v = (
            Validator()
            .required("name", "Alice")
            .max_length("name", "Alice", 100)
            .one_of("role", "admin", ["admin", "user"])
        )
        assert not v.has_errors


# ---------------------------------------------------------------------------
# validate() terminal
# ---------------------------------------------------------------------------


class TestValidate:
    def test_raises_on_errors(self):
        v = Validator().required("name", "").min_length("password", "ab", 8)
        with pytest.raises(InvalidInputError) as exc_info:
            v.validate()
        err = exc_info.value
        assert "name: is required" in err.message
        assert "password:" in err.message
        assert len(err.details["fields"]) == 2

    def test_no_raise_when_valid(self):
        v = Validator().required("name", "Alice")
        assert v.validate() is None


# ---------------------------------------------------------------------------
# validate_model
# ---------------------------------------------------------------------------


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
