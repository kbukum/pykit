"""Comprehensive TDD tests for pykit_validation.

Covers:
- All built-in validators and validation rules
- Validator class / builder API
- FieldError / ValidationError properties
- Multiple validation errors collected simultaneously
- Custom validator functions
- Pydantic model validation integration
- Security: injection via validation messages, ReDoS in regex validators
- Edge cases: empty inputs, unicode, very large inputs, None values, special characters
- Parametrized tests where appropriate
"""

from __future__ import annotations

import re
import time
from dataclasses import FrozenInstanceError
from typing import Optional

import pytest
from pydantic import BaseModel, Field

from pykit_errors import InvalidInputError
from pykit_validation import FieldError, Validator, validate_model


# ===========================================================================
# FieldError dataclass properties
# ===========================================================================


class TestFieldErrorProperties:
    """FieldError is a simple dataclass with field and message."""

    def test_field_and_message_stored(self):
        fe = FieldError(field="email", message="is required")
        assert fe.field == "email"
        assert fe.message == "is required"

    def test_equality(self):
        a = FieldError(field="x", message="y")
        b = FieldError(field="x", message="y")
        assert a == b

    def test_inequality(self):
        a = FieldError(field="x", message="y")
        b = FieldError(field="x", message="z")
        assert a != b

    def test_repr(self):
        fe = FieldError(field="name", message="is required")
        r = repr(fe)
        assert "name" in r
        assert "is required" in r

    def test_hash_not_available_by_default(self):
        """Dataclasses without frozen=True are not hashable."""
        fe = FieldError(field="a", message="b")
        with pytest.raises(TypeError):
            hash(fe)

    def test_field_error_is_mutable(self):
        fe = FieldError(field="a", message="b")
        fe.field = "c"
        assert fe.field == "c"


# ===========================================================================
# Validator introspection & state
# ===========================================================================


class TestValidatorState:
    """Tests for Validator internal state and introspection helpers."""

    def test_fresh_validator_has_no_errors(self):
        v = Validator()
        assert not v.has_errors
        assert v.errors == []

    def test_add_error_manually(self):
        v = Validator()
        v.add_error("f1", "bad")
        assert v.has_errors
        assert len(v.errors) == 1
        assert v.errors[0] == FieldError(field="f1", message="bad")

    def test_errors_returns_copy(self):
        """Mutating the returned list should not affect internal state."""
        v = Validator()
        v.add_error("f", "m")
        errs = v.errors
        errs.clear()
        assert v.has_errors  # internal list unchanged

    def test_multiple_add_error_calls(self):
        v = Validator()
        v.add_error("a", "1")
        v.add_error("b", "2")
        v.add_error("c", "3")
        assert len(v.errors) == 3

    def test_same_field_multiple_errors(self):
        v = Validator()
        v.add_error("password", "too short")
        v.add_error("password", "missing digit")
        assert len(v.errors) == 2
        assert all(e.field == "password" for e in v.errors)


# ===========================================================================
# required() — parametrized
# ===========================================================================


class TestRequiredParametrized:
    @pytest.mark.parametrize(
        "value",
        ["", "   ", "\t", "\n", "\r\n"],
        ids=["empty", "spaces", "tab", "newline", "crlf"],
    )
    def test_blank_values_are_rejected(self, value: str):
        v = Validator().required("name", value)
        assert v.has_errors
        assert v.errors[0].message == "is required"

    @pytest.mark.parametrize(
        "value",
        [0, None, 123, [], False],
        ids=["zero", "none", "int", "list", "false"],
    )
    def test_non_string_values_are_rejected(self, value):
        v = Validator().required("name", value)
        assert v.has_errors

    @pytest.mark.parametrize(
        "value",
        ["a", "hello world", " x ", "0", "False"],
        ids=["single_char", "phrase", "padded", "zero_str", "false_str"],
    )
    def test_non_blank_strings_pass(self, value: str):
        v = Validator().required("name", value)
        assert not v.has_errors


# ===========================================================================
# max_length() — parametrized
# ===========================================================================


class TestMaxLengthParametrized:
    @pytest.mark.parametrize(
        "value, max_len, expect_error",
        [
            ("abc", 3, False),   # exact boundary
            ("ab", 3, False),    # under
            ("abcd", 3, True),   # over by 1
            ("", 0, False),      # empty with 0 limit
            ("a", 0, True),      # 1 char with 0 limit
        ],
        ids=["exact", "under", "over", "empty_zero", "one_char_zero"],
    )
    def test_boundary_cases(self, value: str, max_len: int, expect_error: bool):
        v = Validator().max_length("f", value, max_len)
        assert v.has_errors is expect_error

    def test_unicode_length_is_character_count(self):
        emoji = "🎉🎊🎈"
        v = Validator().max_length("f", emoji, 3)
        assert not v.has_errors
        v2 = Validator().max_length("f", emoji, 2)
        assert v2.has_errors


# ===========================================================================
# min_length() — parametrized
# ===========================================================================


class TestMinLengthParametrized:
    @pytest.mark.parametrize(
        "value, min_len, expect_error",
        [
            ("abc", 3, False),
            ("abcd", 3, False),
            ("ab", 3, True),
            ("", 1, True),
            ("", 0, False),
        ],
        ids=["exact", "over", "under", "empty_one", "empty_zero"],
    )
    def test_boundary_cases(self, value: str, min_len: int, expect_error: bool):
        v = Validator().min_length("f", value, min_len)
        assert v.has_errors is expect_error


# ===========================================================================
# range_check() — parametrized
# ===========================================================================


class TestRangeCheckParametrized:
    @pytest.mark.parametrize(
        "value, lo, hi, expect_error",
        [
            (10, 1, 100, False),
            (1, 1, 100, False),     # low boundary
            (100, 1, 100, False),   # high boundary
            (0, 1, 100, True),      # below
            (101, 1, 100, True),    # above
            (-5, -10, 10, False),
            (0.5, 0.0, 1.0, False),
            (1.01, 0.0, 1.0, True),
        ],
        ids=["mid", "low_bound", "high_bound", "below", "above", "neg", "float_in", "float_out"],
    )
    def test_range_values(self, value, lo, hi, expect_error: bool):
        v = Validator().range_check("f", value, lo, hi)
        assert v.has_errors is expect_error


# ===========================================================================
# min_value() / max_value() — parametrized
# ===========================================================================


class TestMinValueParametrized:
    @pytest.mark.parametrize(
        "value, min_val, expect_error",
        [
            (5, 5, False),
            (6, 5, False),
            (4, 5, True),
            (0, 0, False),
            (-1, 0, True),
            (0.99, 1.0, True),
            (1.0, 1.0, False),
        ],
    )
    def test_min_value(self, value, min_val, expect_error: bool):
        v = Validator().min_value("f", value, min_val)
        assert v.has_errors is expect_error


class TestMaxValueParametrized:
    @pytest.mark.parametrize(
        "value, max_val, expect_error",
        [
            (5, 5, False),
            (4, 5, False),
            (6, 5, True),
            (0, 0, False),
            (1, 0, True),
            (1.01, 1.0, True),
            (1.0, 1.0, False),
        ],
    )
    def test_max_value(self, value, max_val, expect_error: bool):
        v = Validator().max_value("f", value, max_val)
        assert v.has_errors is expect_error


# ===========================================================================
# pattern() — parametrized + edge cases
# ===========================================================================


class TestPatternParametrized:
    EMAIL_RE = r"^[\w.+-]+@[\w-]+\.[\w.]+$"

    @pytest.mark.parametrize(
        "value, regex, expect_error",
        [
            ("hello", r"^hello$", False),
            ("Hello", r"^hello$", True),
            ("abc123", r"^\d+$", True),
            ("123", r"^\d+$", False),
        ],
    )
    def test_various_patterns(self, value: str, regex: str, expect_error: bool):
        v = Validator().pattern("f", value, regex)
        assert v.has_errors is expect_error

    def test_empty_string_is_skipped(self):
        v = Validator().pattern("f", "", r"^will_never_match$")
        assert not v.has_errors

    def test_unicode_value_matches(self):
        v = Validator().pattern("f", "café", r"^café$")
        assert not v.has_errors

    def test_partial_match_succeeds(self):
        """re.search (not re.match) is used, so partial matches succeed."""
        v = Validator().pattern("f", "hello world", r"world")
        assert not v.has_errors


# ===========================================================================
# one_of() — parametrized + edge cases
# ===========================================================================


class TestOneOfParametrized:
    @pytest.mark.parametrize(
        "value, allowed, expect_error",
        [
            ("a", ["a", "b", "c"], False),
            ("d", ["a", "b", "c"], True),
            ("A", ["a", "b", "c"], True),   # case-sensitive
            ("", ["a", "b"], False),          # empty skipped
        ],
    )
    def test_one_of_values(self, value: str, allowed: list[str], expect_error: bool):
        v = Validator().one_of("f", value, allowed)
        assert v.has_errors is expect_error

    def test_single_allowed_value(self):
        v = Validator().one_of("f", "x", ["x"])
        assert not v.has_errors

    def test_error_message_lists_allowed(self):
        v = Validator().one_of("role", "boss", ["admin", "user"])
        assert v.errors[0].message == "must be one of: admin, user"


# ===========================================================================
# custom() — parametrized
# ===========================================================================


class TestCustomParametrized:
    @pytest.mark.parametrize(
        "condition, expect_error",
        [(True, False), (False, True)],
    )
    def test_condition(self, condition: bool, expect_error: bool):
        v = Validator().custom(condition, "f", "msg")
        assert v.has_errors is expect_error

    def test_custom_with_lambda_logic(self):
        """Custom can be used with inline boolean expressions."""
        password = "abc"
        has_digit = any(c.isdigit() for c in password)
        v = Validator().custom(has_digit, "password", "must contain a digit")
        assert v.has_errors
        assert v.errors[0].message == "must contain a digit"

    def test_custom_passes_complex_condition(self):
        data = {"start": 1, "end": 10}
        v = Validator().custom(data["start"] < data["end"], "range", "start must be < end")
        assert not v.has_errors


# ===========================================================================
# Chaining & multiple error accumulation
# ===========================================================================


class TestChainingComprehensive:
    def test_all_validators_in_chain(self):
        v = (
            Validator()
            .required("name", "")
            .max_length("bio", "x" * 300, 255)
            .min_length("password", "ab", 8)
            .range_check("age", 200, 0, 150)
            .min_value("score", -1, 0)
            .max_value("level", 11, 10)
            .pattern("email", "bad", r"^.+@.+$")
            .one_of("role", "boss", ["admin", "user"])
            .custom(False, "tos", "must accept terms")
        )
        assert len(v.errors) == 9
        fields = [e.field for e in v.errors]
        assert fields == ["name", "bio", "password", "age", "score", "level", "email", "role", "tos"]

    def test_chaining_returns_same_validator(self):
        v = Validator()
        result = v.required("a", "ok")
        assert result is v

    def test_chaining_preserves_order(self):
        v = Validator().required("first", "").required("second", "").required("third", "")
        fields = [e.field for e in v.errors]
        assert fields == ["first", "second", "third"]


# ===========================================================================
# validate() terminal — error structure
# ===========================================================================


class TestValidateTerminal:
    def test_raises_invalid_input_error(self):
        v = Validator().required("name", "")
        with pytest.raises(InvalidInputError):
            v.validate()

    def test_error_message_contains_all_fields(self):
        v = Validator().required("name", "").required("email", "")
        with pytest.raises(InvalidInputError) as exc_info:
            v.validate()
        msg = exc_info.value.message
        assert "name: is required" in msg
        assert "email: is required" in msg
        assert ";" in msg  # semicolon separator

    def test_error_details_structure(self):
        v = Validator().required("name", "").min_length("pw", "ab", 8)
        with pytest.raises(InvalidInputError) as exc_info:
            v.validate()
        details = exc_info.value.details
        assert "fields" in details
        assert len(details["fields"]) == 2
        assert details["fields"][0] == {"field": "name", "message": "is required"}
        assert details["fields"][1] == {"field": "pw", "message": "must be at least 8 characters"}

    def test_no_raise_returns_none(self):
        v = Validator().required("name", "Alice")
        assert v.validate() is None

    def test_error_is_exception_subclass(self):
        v = Validator().required("name", "")
        with pytest.raises(Exception):
            v.validate()

    def test_single_error_no_semicolon(self):
        v = Validator().required("name", "")
        with pytest.raises(InvalidInputError) as exc_info:
            v.validate()
        assert ";" not in exc_info.value.message


# ===========================================================================
# Multiple errors collected simultaneously
# ===========================================================================


class TestMultipleErrorsCollected:
    def test_collect_errors_for_same_field(self):
        password = "ab"
        v = (
            Validator()
            .min_length("password", password, 8)
            .custom(any(c.isdigit() for c in password), "password", "must contain a digit")
            .custom(any(c.isupper() for c in password), "password", "must contain uppercase")
        )
        assert len(v.errors) == 3
        assert all(e.field == "password" for e in v.errors)

    def test_collect_errors_across_many_fields(self):
        v = Validator()
        for i in range(20):
            v.add_error(f"field_{i}", f"error {i}")
        assert len(v.errors) == 20

    def test_validate_includes_all_collected_errors(self):
        v = Validator()
        v.add_error("a", "msg_a")
        v.add_error("b", "msg_b")
        v.add_error("c", "msg_c")
        with pytest.raises(InvalidInputError) as exc_info:
            v.validate()
        assert len(exc_info.value.details["fields"]) == 3


# ===========================================================================
# Custom validator functions (using custom())
# ===========================================================================


class TestCustomValidatorFunctions:
    def test_password_strength_validator(self):
        def validate_password(v: Validator, password: str) -> Validator:
            v.min_length("password", password, 8)
            v.custom(any(c.isdigit() for c in password), "password", "must contain a digit")
            v.custom(any(c.isupper() for c in password), "password", "must contain uppercase")
            v.custom(
                any(c in "!@#$%^&*()" for c in password),
                "password",
                "must contain special character",
            )
            return v

        v = validate_password(Validator(), "short")
        assert len(v.errors) == 4

        v2 = validate_password(Validator(), "Strong1!xx")
        assert not v2.has_errors

    def test_date_range_validator(self):
        start, end = 10, 5
        v = Validator().custom(start < end, "dates", "start must be before end")
        assert v.has_errors

    def test_conditional_validation(self):
        """Validate a field only when another field has a specific value."""
        role = "admin"
        admin_code = ""
        v = Validator().required("role", role)
        if role == "admin":
            v.required("admin_code", admin_code)
        assert len(v.errors) == 1
        assert v.errors[0].field == "admin_code"


# ===========================================================================
# Pydantic model validation (validate_model)
# ===========================================================================


class _SimpleModel(BaseModel):
    name: str = Field(..., min_length=1)
    age: int = Field(..., ge=0, le=150)


class _NestedAddress(BaseModel):
    street: str
    city: str


class _NestedModel(BaseModel):
    name: str
    address: _NestedAddress


class _OptionalFieldsModel(BaseModel):
    name: str
    bio: Optional[str] = None
    age: Optional[int] = None


class _StrictModel(BaseModel):
    count: int
    label: str = Field(..., pattern=r"^[a-z]+$")


class TestValidateModelComprehensive:
    def test_valid_data_returns_instance(self):
        result = validate_model(_SimpleModel, {"name": "Alice", "age": 30})
        assert isinstance(result, _SimpleModel)
        assert result.name == "Alice"
        assert result.age == 30

    def test_missing_all_required_fields(self):
        with pytest.raises(InvalidInputError) as exc_info:
            validate_model(_SimpleModel, {})
        err = exc_info.value
        assert len(err.details["fields"]) >= 2

    def test_type_coercion(self):
        """Pydantic coerces compatible types."""
        result = validate_model(_SimpleModel, {"name": "Bob", "age": "25"})
        assert result.age == 25

    def test_invalid_type_no_coercion(self):
        with pytest.raises(InvalidInputError):
            validate_model(_SimpleModel, {"name": "Bob", "age": "not_a_number"})

    def test_constraint_violation(self):
        with pytest.raises(InvalidInputError) as exc_info:
            validate_model(_SimpleModel, {"name": "", "age": -1})
        field_names = {f["field"] for f in exc_info.value.details["fields"]}
        assert "name" in field_names
        assert "age" in field_names

    def test_nested_model_valid(self):
        data = {"name": "Alice", "address": {"street": "123 Main", "city": "NYC"}}
        result = validate_model(_NestedModel, data)
        assert result.address.city == "NYC"

    def test_nested_model_missing_inner_fields(self):
        with pytest.raises(InvalidInputError) as exc_info:
            validate_model(_NestedModel, {"name": "Alice", "address": {}})
        fields = {f["field"] for f in exc_info.value.details["fields"]}
        assert any("street" in f for f in fields)

    def test_nested_model_wrong_type(self):
        with pytest.raises(InvalidInputError):
            validate_model(_NestedModel, {"name": "Alice", "address": "not a dict"})

    def test_optional_fields_can_be_omitted(self):
        result = validate_model(_OptionalFieldsModel, {"name": "Alice"})
        assert result.bio is None
        assert result.age is None

    def test_optional_fields_can_be_provided(self):
        result = validate_model(_OptionalFieldsModel, {"name": "Alice", "bio": "Hi", "age": 25})
        assert result.bio == "Hi"
        assert result.age == 25

    def test_error_message_format(self):
        """Error message joins field messages with semicolons."""
        with pytest.raises(InvalidInputError) as exc_info:
            validate_model(_SimpleModel, {})
        msg = exc_info.value.message
        assert ";" in msg or ":" in msg  # at least structured

    def test_error_is_chained_from_validation_error(self):
        """The InvalidInputError should chain from the original Pydantic error."""
        with pytest.raises(InvalidInputError) as exc_info:
            validate_model(_SimpleModel, {})
        assert exc_info.value.__cause__ is not None

    def test_pattern_field_validation(self):
        with pytest.raises(InvalidInputError):
            validate_model(_StrictModel, {"count": 1, "label": "UPPER"})

    def test_extra_fields_ignored(self):
        """By default Pydantic ignores extra fields."""
        result = validate_model(_SimpleModel, {"name": "A", "age": 1, "extra": "ignored"})
        assert result.name == "A"


# ===========================================================================
# Security: injection via validation messages
# ===========================================================================


class TestSecurityInjection:
    def test_html_in_field_name_preserved_literally(self):
        """Field names with HTML should not be interpreted."""
        v = Validator().required("<script>alert(1)</script>", "")
        err = v.errors[0]
        assert err.field == "<script>alert(1)</script>"
        assert "<script>" in err.field  # literal, not executed

    def test_html_in_value_preserved(self):
        v = Validator().one_of("role", "<img onerror=alert(1)>", ["admin"])
        assert v.has_errors
        # The error message includes allowed values, not the input

    def test_sql_injection_in_field_name(self):
        v = Validator().required("'; DROP TABLE users; --", "")
        assert v.errors[0].field == "'; DROP TABLE users; --"

    def test_null_bytes_in_value(self):
        v = Validator().required("name", "hello\x00world")
        assert not v.has_errors  # non-blank string

    def test_unicode_control_characters(self):
        v = Validator().required("name", "\u200b")  # zero-width space
        # This is technically a non-blank string (strip() doesn't remove ZWSP)
        assert not v.has_errors

    def test_injection_in_custom_message(self):
        """Custom messages are stored literally."""
        msg = "<script>alert('xss')</script>"
        v = Validator().custom(False, "f", msg)
        assert v.errors[0].message == msg

    def test_validate_error_message_preserves_special_chars(self):
        v = Validator()
        v.add_error("f", "msg with 'quotes' and \"doubles\"")
        with pytest.raises(InvalidInputError) as exc_info:
            v.validate()
        assert "quotes" in exc_info.value.message

    def test_pydantic_model_injection_in_data(self):
        """Malicious data values should result in proper errors."""
        with pytest.raises(InvalidInputError):
            validate_model(
                _SimpleModel,
                {"name": "<script>alert(1)</script>", "age": "'; DROP TABLE users;"},
            )


# ===========================================================================
# Security: ReDoS in regex validators
# ===========================================================================


class TestReDoSSecurity:
    def test_safe_pattern_completes_fast(self):
        """A simple regex should complete near-instantly."""
        start = time.monotonic()
        v = Validator().pattern("f", "a" * 100, r"^[a-z]+$")
        elapsed = time.monotonic() - start
        assert elapsed < 1.0
        assert not v.has_errors

    def test_potentially_evil_input_does_not_hang(self):
        """Validate that a moderately complex pattern doesn't freeze on crafted input.

        This uses a non-backtracking-safe pattern. Python's re module can be slow
        on certain inputs, but we verify it completes within a reasonable time for
        inputs of modest length.
        """
        # Pattern: nested quantifiers that can cause catastrophic backtracking
        evil_pattern = r"^(a+)+$"
        # Input designed to trigger backtracking: 'a' * N + '!'
        crafted_input = "a" * 25 + "!"

        start = time.monotonic()
        v = Validator().pattern("f", crafted_input, evil_pattern)
        elapsed = time.monotonic() - start

        assert v.has_errors  # should not match
        # We allow 5 seconds; a true ReDoS would take minutes/hours at length 25+
        assert elapsed < 5.0, f"Pattern took {elapsed:.2f}s — potential ReDoS"


# ===========================================================================
# Edge cases: empty, None, unicode, large inputs, special chars
# ===========================================================================


class TestEdgeCasesEmpty:
    def test_empty_string_max_length_zero(self):
        v = Validator().max_length("f", "", 0)
        assert not v.has_errors

    def test_empty_string_min_length_zero(self):
        v = Validator().min_length("f", "", 0)
        assert not v.has_errors

    def test_pattern_empty_skipped(self):
        v = Validator().pattern("f", "", r"^impossible$")
        assert not v.has_errors

    def test_one_of_empty_skipped(self):
        v = Validator().one_of("f", "", ["x"])
        assert not v.has_errors

    def test_no_validators_validate_passes(self):
        v = Validator()
        assert v.validate() is None


class TestEdgeCasesUnicode:
    @pytest.mark.parametrize(
        "value",
        ["héllo", "日本語", "مرحبا", "🎉🎊🎈", "café", "naïve"],
        ids=["french", "japanese", "arabic", "emoji", "cafe", "naive"],
    )
    def test_required_accepts_unicode(self, value: str):
        v = Validator().required("f", value)
        assert not v.has_errors

    def test_max_length_counts_unicode_chars(self):
        v = Validator().max_length("f", "日本語", 3)
        assert not v.has_errors

    def test_min_length_counts_unicode_chars(self):
        v = Validator().min_length("f", "日本", 2)
        assert not v.has_errors

    def test_pattern_with_unicode(self):
        v = Validator().pattern("f", "café", r"café")
        assert not v.has_errors

    def test_one_of_with_unicode(self):
        v = Validator().one_of("lang", "日本語", ["English", "日本語", "Español"])
        assert not v.has_errors


class TestEdgeCasesLargeInputs:
    def test_very_large_string_max_length(self):
        big = "x" * 1_000_000
        v = Validator().max_length("f", big, 100)
        assert v.has_errors

    def test_very_large_string_min_length(self):
        big = "x" * 1_000_000
        v = Validator().min_length("f", big, 100)
        assert not v.has_errors

    def test_very_large_string_required(self):
        big = "x" * 1_000_000
        v = Validator().required("f", big)
        assert not v.has_errors

    def test_very_large_number_range(self):
        v = Validator().range_check("f", 10**18, 0, 10**18)
        assert not v.has_errors

    def test_many_errors_collected(self):
        v = Validator()
        for i in range(1000):
            v.required(f"field_{i}", "")
        assert len(v.errors) == 1000
        with pytest.raises(InvalidInputError) as exc_info:
            v.validate()
        assert len(exc_info.value.details["fields"]) == 1000


class TestEdgeCasesNone:
    def test_required_none(self):
        v = Validator().required("f", None)
        assert v.has_errors

    def test_required_false(self):
        v = Validator().required("f", False)
        assert v.has_errors

    def test_required_zero(self):
        v = Validator().required("f", 0)
        assert v.has_errors


class TestEdgeCasesSpecialCharacters:
    @pytest.mark.parametrize(
        "value",
        [
            "hello\nworld",
            "tab\there",
            "null\x00byte",
            "back\\slash",
            'double"quote',
            "single'quote",
        ],
        ids=["newline", "tab", "null_byte", "backslash", "double_quote", "single_quote"],
    )
    def test_required_accepts_special_chars(self, value: str):
        v = Validator().required("f", value)
        assert not v.has_errors

    def test_one_of_with_special_chars(self):
        v = Validator().one_of("f", "a\nb", ["a\nb", "c"])
        assert not v.has_errors

    def test_max_length_with_newlines(self):
        v = Validator().max_length("f", "a\nb\nc", 5)
        assert not v.has_errors


# ===========================================================================
# Validator builder pattern / fluent API
# ===========================================================================


class TestBuilderAPI:
    def test_all_methods_return_validator(self):
        """Every chainable method must return the same Validator instance."""
        v = Validator()
        assert v.required("a", "x") is v
        assert v.max_length("a", "x", 10) is v
        assert v.min_length("a", "x", 1) is v
        assert v.range_check("a", 5, 0, 10) is v
        assert v.min_value("a", 5, 0) is v
        assert v.max_value("a", 5, 10) is v
        assert v.pattern("a", "x", r"x") is v
        assert v.one_of("a", "x", ["x"]) is v
        assert v.custom(True, "a", "m") is v

    def test_builder_can_be_reused_across_validations(self):
        """A single validator accumulates all errors from successive calls."""
        v = Validator()
        v.required("a", "")
        v.required("b", "")
        assert len(v.errors) == 2

    def test_independent_validators_do_not_share_state(self):
        v1 = Validator().required("a", "")
        v2 = Validator().required("b", "ok")
        assert v1.has_errors
        assert not v2.has_errors


# ===========================================================================
# validate_model — additional edge cases
# ===========================================================================


class _EmptyModel(BaseModel):
    pass


class _AllOptionalModel(BaseModel):
    x: Optional[str] = None
    y: Optional[int] = None


class _DefaultValueModel(BaseModel):
    name: str = "default"
    count: int = 0


class TestValidateModelEdgeCases:
    def test_empty_model_accepts_empty_dict(self):
        result = validate_model(_EmptyModel, {})
        assert isinstance(result, _EmptyModel)

    def test_all_optional_model(self):
        result = validate_model(_AllOptionalModel, {})
        assert result.x is None
        assert result.y is None

    def test_default_values_applied(self):
        result = validate_model(_DefaultValueModel, {})
        assert result.name == "default"
        assert result.count == 0

    def test_default_values_overridden(self):
        result = validate_model(_DefaultValueModel, {"name": "custom", "count": 42})
        assert result.name == "custom"
        assert result.count == 42

    def test_empty_dict_with_required_fields_fails(self):
        with pytest.raises(InvalidInputError):
            validate_model(_SimpleModel, {})

    def test_nested_field_name_in_error(self):
        """Nested Pydantic errors should show dotted field paths."""
        with pytest.raises(InvalidInputError) as exc_info:
            validate_model(_NestedModel, {"name": "A", "address": {}})
        fields = [f["field"] for f in exc_info.value.details["fields"]]
        # Nested fields produce dotted paths like "address.street"
        assert any("." in f for f in fields)
