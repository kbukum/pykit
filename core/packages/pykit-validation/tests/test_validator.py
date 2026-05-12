"""Tests for Validator chainable field validation."""

from __future__ import annotations

import pytest

from pykit_errors import InvalidInputError
from pykit_validation import FieldError, Validator


class TestRequired:
    def test_none(self):
        v = Validator().required("name", None)
        assert v.has_errors
        assert v.errors[0] == FieldError(field="name", message="is required")

    def test_empty_string(self):
        v = Validator().required("name", "")
        assert v.has_errors

    def test_whitespace_only(self):
        v = Validator().required("name", "   ")
        assert v.has_errors

    def test_valid_string(self):
        v = Validator().required("name", "Alice")
        assert not v.has_errors

    def test_empty_list(self):
        v = Validator().required("tags", [])
        assert v.has_errors

    def test_non_empty_list(self):
        v = Validator().required("tags", ["a"])
        assert not v.has_errors

    def test_empty_dict(self):
        v = Validator().required("meta", {})
        assert v.has_errors

    def test_non_empty_dict(self):
        v = Validator().required("meta", {"k": "v"})
        assert not v.has_errors

    def test_zero_is_valid(self):
        v = Validator().required("count", 0)
        assert not v.has_errors

    def test_false_is_valid(self):
        v = Validator().required("flag", False)
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

    def test_exact_boundary(self):
        v = Validator().min_length("password", "abcdefgh", 8)
        assert not v.has_errors


class TestRangeCheck:
    def test_below(self):
        v = Validator().in_range("age", 5, 18, 120)
        assert v.has_errors
        assert "between 18 and 120" in v.errors[0].message

    def test_above(self):
        v = Validator().in_range("age", 200, 18, 120)
        assert v.has_errors

    def test_within(self):
        v = Validator().in_range("age", 25, 18, 120)
        assert not v.has_errors

    def test_boundaries(self):
        assert not Validator().in_range("age", 18, 18, 120).has_errors
        assert not Validator().in_range("age", 120, 18, 120).has_errors


class TestPattern:
    def test_no_match(self):
        v = Validator().pattern("code", "abc", r"^[A-Z]+$")
        assert v.has_errors
        assert "does not match required format" in v.errors[0].message

    def test_match(self):
        v = Validator().pattern("code", "ABC", r"^[A-Z]+$")
        assert not v.has_errors

    def test_empty_skipped(self):
        v = Validator().pattern("code", "", r"^[A-Z]+$")
        assert not v.has_errors


class TestOneOf:
    def test_invalid(self):
        v = Validator().one_of("role", "superadmin", ["admin", "user"])
        assert v.has_errors
        assert "must be one of: admin, user" in v.errors[0].message

    def test_valid(self):
        v = Validator().one_of("role", "admin", ["admin", "user"])
        assert not v.has_errors

    def test_empty_skipped(self):
        v = Validator().one_of("role", "", ["admin"])
        assert not v.has_errors


class TestCustom:
    def test_false_condition(self):
        v = Validator().custom(False, "field", "custom error")
        assert v.has_errors
        assert v.errors[0].message == "custom error"

    def test_true_condition(self):
        v = Validator().custom(True, "field", "custom error")
        assert not v.has_errors


class TestUuid:
    def test_valid(self):
        v = Validator().required_uuid("id", "550e8400-e29b-41d4-a716-446655440000")
        assert not v.has_errors

    def test_invalid(self):
        v = Validator().required_uuid("id", "not-a-uuid")
        assert v.has_errors
        assert "must be a valid UUID" in v.errors[0].message

    def test_empty_required_fails(self):
        v = Validator().required_uuid("id", "")
        assert v.has_errors
        assert "is required" in v.errors[0].message

    def test_optional_empty_skipped(self):
        v = Validator().optional_uuid("id", "")
        assert not v.has_errors

    def test_optional_none_skipped(self):
        v = Validator().optional_uuid("id", None)
        assert not v.has_errors

    def test_optional_invalid(self):
        v = Validator().optional_uuid("id", "not-a-uuid")
        assert v.has_errors

    def test_nil_uuid(self):
        v = Validator().required_uuid("id", "00000000-0000-0000-0000-000000000000")
        assert not v.has_errors


class TestEmail:
    def test_valid(self):
        v = Validator().email("email", "user@example.com")
        assert not v.has_errors

    def test_valid_with_plus(self):
        v = Validator().email("email", "user+tag@example.com")
        assert not v.has_errors

    def test_invalid_no_at(self):
        v = Validator().email("email", "userexample.com")
        assert v.has_errors
        assert "must be a valid email address" in v.errors[0].message

    def test_invalid_no_domain(self):
        v = Validator().email("email", "user@")
        assert v.has_errors

    def test_invalid_no_tld(self):
        v = Validator().email("email", "user@example")
        assert v.has_errors

    def test_empty_skipped(self):
        v = Validator().email("email", "")
        assert not v.has_errors


class TestUrl:
    def test_valid_http(self):
        assert not Validator().url("u", "http://example.com").has_errors

    def test_valid_https(self):
        assert not Validator().url("u", "https://example.com/path?q=1").has_errors

    def test_invalid_scheme(self):
        v = Validator().url("u", "ftp://example.com")
        assert v.has_errors
        assert "must be a valid URL" in v.errors[0].message

    def test_empty_skipped(self):
        assert not Validator().url("u", "").has_errors


class TestBeforeAfter:
    def test_before_passes(self):
        assert not Validator().before("t", "2024-01-01T00:00:00Z", "2025-01-01T00:00:00Z").has_errors

    def test_before_fails_when_equal(self):
        v = Validator().before("t", "2025-01-01T00:00:00Z", "2025-01-01T00:00:00Z")
        assert v.has_errors

    def test_before_fails_when_after(self):
        v = Validator().before("t", "2026-01-01T00:00:00Z", "2025-01-01T00:00:00Z")
        assert v.has_errors

    def test_before_invalid_datetime(self):
        v = Validator().before("t", "not-a-date", "2025-01-01T00:00:00Z")
        assert v.has_errors
        assert "valid datetime" in v.errors[0].message

    def test_before_empty_skipped(self):
        assert not Validator().before("t", "", "2025-01-01T00:00:00Z").has_errors

    def test_after_passes(self):
        assert not Validator().after("t", "2026-01-01T00:00:00Z", "2025-01-01T00:00:00Z").has_errors

    def test_after_fails_when_equal(self):
        v = Validator().after("t", "2025-01-01T00:00:00Z", "2025-01-01T00:00:00Z")
        assert v.has_errors

    def test_after_fails_when_before(self):
        v = Validator().after("t", "2024-01-01T00:00:00Z", "2025-01-01T00:00:00Z")
        assert v.has_errors

    def test_after_empty_skipped(self):
        assert not Validator().after("t", "", "2025-01-01T00:00:00Z").has_errors


class TestChaining:
    def test_multiple_errors(self):
        v = (
            Validator()
            .required("name", "")
            .min_length("password", "ab", 8)
            .one_of("role", "x", ["admin", "user"])
        )
        assert len(v.errors) == 3

    def test_no_errors(self):
        v = (
            Validator()
            .required("name", "Alice")
            .max_length("name", "Alice", 100)
            .email("email", "a@b.com")
            .required_uuid("id", "550e8400-e29b-41d4-a716-446655440000")
        )
        assert not v.has_errors


class TestValidate:
    def test_raises_on_errors(self):
        v = Validator().required("name", "").min_length("password", "ab", 8)
        with pytest.raises(InvalidInputError) as exc_info:
            v.validate()
        err = exc_info.value
        assert "name: is required" in err.message
        assert len(err.details["fields"]) == 2

    def test_no_raise_when_valid(self):
        v = Validator().required("name", "Alice")
        assert v.validate() is None
