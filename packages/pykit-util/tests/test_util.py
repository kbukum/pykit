"""Comprehensive tests for pykit-util."""

from __future__ import annotations

import pytest

from pykit_util.collections import chunk, first, flatten, group_by, unique
from pykit_util.merge import deep_merge
from pykit_util.parse import mask_secret, parse_bool, parse_size
from pykit_util.sanitize import is_safe_string, sanitize_env_value, sanitize_string
from pykit_util.strings import coalesce, slug, truncate

# ── collections ──────────────────────────────────────────────────────────


class TestFirst:
    def test_no_predicate(self):
        assert first([10, 20, 30]) == 10

    def test_with_predicate(self):
        assert first([1, 2, 3, 4], predicate=lambda x: x > 2) == 3

    def test_no_match_returns_default(self):
        assert first([1, 2], predicate=lambda x: x > 10, default=-1) == -1

    def test_empty_iterable(self):
        assert first([]) is None

    def test_empty_iterable_custom_default(self):
        assert first([], default=42) == 42

    def test_generator(self):
        assert first(x for x in range(5) if x > 2) == 3


class TestUnique:
    def test_basic(self):
        assert unique([1, 2, 2, 3, 1]) == [1, 2, 3]

    def test_preserves_order(self):
        assert unique([3, 1, 2, 1, 3]) == [3, 1, 2]

    def test_empty(self):
        assert unique([]) == []

    def test_all_same(self):
        assert unique([7, 7, 7]) == [7]

    def test_strings(self):
        assert unique(["a", "b", "a", "c"]) == ["a", "b", "c"]


class TestChunk:
    def test_even_split(self):
        assert chunk([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]

    def test_uneven_split(self):
        assert chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]

    def test_single_chunk(self):
        assert chunk([1, 2], 10) == [[1, 2]]

    def test_empty(self):
        assert chunk([], 3) == []

    def test_size_one(self):
        assert chunk([1, 2, 3], 1) == [[1], [2], [3]]

    def test_invalid_size(self):
        with pytest.raises(ValueError, match="positive"):
            chunk([1], 0)

    def test_negative_size(self):
        with pytest.raises(ValueError, match="positive"):
            chunk([1], -1)


class TestFlatten:
    def test_basic(self):
        assert flatten([[1, 2], [3, 4]]) == [1, 2, 3, 4]

    def test_empty_sublists(self):
        assert flatten([[], [1], []]) == [1]

    def test_empty(self):
        assert flatten([]) == []

    def test_single_level_only(self):
        assert flatten([[[1, 2]], [3]]) == [[1, 2], 3]


class TestGroupBy:
    def test_basic(self):
        result = group_by(["ant", "bee", "ape"], key_fn=lambda s: s[0])
        assert result == {"a": ["ant", "ape"], "b": ["bee"]}

    def test_numbers(self):
        result = group_by([1, 2, 3, 4, 5, 6], key_fn=lambda x: x % 2)
        assert result == {1: [1, 3, 5], 0: [2, 4, 6]}

    def test_empty(self):
        assert group_by([], key_fn=lambda x: x) == {}


# ── strings ──────────────────────────────────────────────────────────────


class TestCoalesce:
    def test_first_truthy(self):
        assert coalesce(None, "", "hello") == "hello"

    def test_all_falsy(self):
        assert coalesce(None, "", 0) is None

    def test_first_value_truthy(self):
        assert coalesce("first", "second") == "first"

    def test_zero_vs_none(self):
        assert coalesce(0, None, 42) == 42

    def test_no_args(self):
        assert coalesce() is None


class TestSlug:
    def test_basic(self):
        assert slug("Hello World") == "hello-world"

    def test_special_chars(self):
        assert slug("Hello, World! #2024") == "hello-world-2024"

    def test_unicode(self):
        assert slug("Héllo Wörld") == "hello-world"

    def test_multiple_spaces(self):
        assert slug("  hello   world  ") == "hello-world"

    def test_already_slug(self):
        assert slug("already-a-slug") == "already-a-slug"

    def test_empty(self):
        assert slug("") == ""


class TestTruncate:
    def test_no_truncation_needed(self):
        assert truncate("hi", 10) == "hi"

    def test_exact_length(self):
        assert truncate("hello", 5) == "hello"

    def test_truncation(self):
        assert truncate("hello world", 8) == "hello..."

    def test_custom_suffix(self):
        assert truncate("hello world", 8, suffix="~") == "hello w~"

    def test_max_len_less_than_suffix(self):
        assert truncate("hello world", 2) == "he"

    def test_empty(self):
        assert truncate("", 5) == ""


# ── parse ────────────────────────────────────────────────────────────────


class TestParseSize:
    def test_bytes(self):
        assert parse_size("100B") == 100

    def test_kilobytes(self):
        assert parse_size("10KB") == 10 * 1024

    def test_megabytes(self):
        assert parse_size("10MB") == 10 * 1024**2

    def test_gigabytes(self):
        assert parse_size("2GB") == 2 * 1024**3

    def test_terabytes(self):
        assert parse_size("1TB") == 1024**4

    def test_no_unit(self):
        assert parse_size("512") == 512

    def test_whitespace(self):
        assert parse_size("  512 KB  ") == 512 * 1024

    def test_case_insensitive(self):
        assert parse_size("10mb") == 10 * 1024**2

    def test_decimal(self):
        assert parse_size("1.5GB") == int(1.5 * 1024**3)

    def test_invalid_returns_default(self):
        assert parse_size("abc") == 0

    def test_invalid_custom_default(self):
        assert parse_size("abc", default=-1) == -1


class TestMaskSecret:
    def test_basic(self):
        assert mask_secret("abcdefgh") == "abcd***"

    def test_short_secret(self):
        assert mask_secret("abc") == "***"

    def test_exact_prefix(self):
        assert mask_secret("abcd") == "***"

    def test_custom_prefix(self):
        assert mask_secret("abcdefgh", visible_prefix=2) == "ab***"

    def test_empty(self):
        assert mask_secret("") == "***"


class TestParseBool:
    @pytest.mark.parametrize("value", ["true", "True", "TRUE", "yes", "Yes", "1", "on", "t", "y"])
    def test_truthy(self, value: str):
        assert parse_bool(value) is True

    @pytest.mark.parametrize("value", ["false", "False", "FALSE", "no", "No", "0", "off", "f", "n", ""])
    def test_falsy(self, value: str):
        assert parse_bool(value) is False

    def test_whitespace(self):
        assert parse_bool("  true  ") is True

    def test_invalid(self):
        with pytest.raises(ValueError, match="cannot parse"):
            parse_bool("maybe")


# ── sanitize ─────────────────────────────────────────────────────────────


class TestSanitizeString:
    def test_strips_whitespace(self):
        assert sanitize_string("  hello  ") == "hello"

    def test_removes_control_chars(self):
        assert sanitize_string("hel\x00lo\x01") == "hello"

    def test_preserves_newlines(self):
        assert sanitize_string("hello\nworld") == "hello\nworld"

    def test_preserves_tabs(self):
        assert sanitize_string("hello\tworld") == "hello\tworld"

    def test_unicode_normalization(self):
        # ñ can be composed or decomposed; should normalize
        composed = "\u00f1"  # ñ
        decomposed = "n\u0303"  # n + combining tilde
        assert sanitize_string(composed) == sanitize_string(decomposed)


class TestSanitizeEnvValue:
    def test_strips_double_quotes(self):
        assert sanitize_env_value('"hello"') == "hello"

    def test_strips_single_quotes(self):
        assert sanitize_env_value("'hello'") == "hello"

    def test_strips_whitespace(self):
        assert sanitize_env_value("  hello  ") == "hello"

    def test_combined(self):
        assert sanitize_env_value('  "hello"  ') == "hello"

    def test_mismatched_quotes_preserved(self):
        assert sanitize_env_value("\"hello'") == "\"hello'"

    def test_empty_quotes(self):
        assert sanitize_env_value('""') == ""

    def test_single_char(self):
        assert sanitize_env_value("x") == "x"


class TestIsSafeString:
    def test_safe_string(self):
        assert is_safe_string("hello world") is True

    def test_sql_injection(self):
        assert is_safe_string("-- drop table users") is False

    def test_sql_union(self):
        assert is_safe_string("; select * from users") is False

    def test_shell_injection(self):
        assert is_safe_string("$(whoami)") is False

    def test_backtick_injection(self):
        assert is_safe_string("`$(whoami)`") is False

    def test_path_traversal(self):
        assert is_safe_string("../../etc/passwd") is False

    def test_script_tag(self):
        assert is_safe_string("<script>alert(1)</script>") is False

    def test_normal_html(self):
        assert is_safe_string("<div>hello</div>") is True

    def test_empty(self):
        assert is_safe_string("") is True


# ── merge ────────────────────────────────────────────────────────────────


class TestDeepMerge:
    def test_flat(self):
        assert deep_merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}

    def test_override(self):
        assert deep_merge({"a": 1}, {"a": 2}) == {"a": 2}

    def test_nested(self):
        base = {"a": {"x": 1, "y": 2}}
        override = {"a": {"y": 3, "z": 4}}
        assert deep_merge(base, override) == {"a": {"x": 1, "y": 3, "z": 4}}

    def test_deep_nested(self):
        base = {"a": {"b": {"c": 1}}}
        override = {"a": {"b": {"d": 2}}}
        assert deep_merge(base, override) == {"a": {"b": {"c": 1, "d": 2}}}

    def test_override_dict_with_scalar(self):
        assert deep_merge({"a": {"x": 1}}, {"a": 42}) == {"a": 42}

    def test_override_scalar_with_dict(self):
        assert deep_merge({"a": 1}, {"a": {"x": 2}}) == {"a": {"x": 2}}

    def test_does_not_mutate_base(self):
        base = {"a": {"x": 1}}
        override = {"a": {"y": 2}}
        deep_merge(base, override)
        assert base == {"a": {"x": 1}}

    def test_empty_base(self):
        assert deep_merge({}, {"a": 1}) == {"a": 1}

    def test_empty_override(self):
        assert deep_merge({"a": 1}, {}) == {"a": 1}

    def test_both_empty(self):
        assert deep_merge({}, {}) == {}


# ── __init__ re-exports ─────────────────────────────────────────────────


class TestReExports:
    """Verify that the top-level package re-exports every public function."""

    def test_all_exports(self):
        import pykit_util

        expected = [
            "chunk",
            "first",
            "flatten",
            "group_by",
            "unique",
            "coalesce",
            "slug",
            "truncate",
            "mask_secret",
            "parse_bool",
            "parse_size",
            "is_safe_string",
            "sanitize_env_value",
            "sanitize_string",
            "deep_merge",
        ]
        for name in expected:
            assert hasattr(pykit_util, name), f"pykit_util missing export: {name}"
