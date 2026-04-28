"""Tests for pykit_util string utilities."""

from pykit_util import coalesce, slug, truncate


class TestCoalesce:
    def test_returns_first_non_none(self) -> None:
        assert coalesce(None, None, "hello", "world") == "hello"

    def test_returns_none_when_all_none(self) -> None:
        assert coalesce(None, None) is None

    def test_preserves_zero(self) -> None:
        assert coalesce(None, 0, 42) == 0

    def test_preserves_empty_string(self) -> None:
        assert coalesce(None, "", "fallback") == ""

    def test_preserves_false(self) -> None:
        assert coalesce(None, False, True) is False

    def test_no_args(self) -> None:
        assert coalesce() is None

    def test_single_value(self) -> None:
        assert coalesce(42) == 42


class TestSlug:
    def test_basic(self) -> None:
        assert slug("Hello World") == "hello-world"

    def test_special_characters(self) -> None:
        assert slug("Hello & World!") == "hello-world"

    def test_unicode(self) -> None:
        assert slug("Héllo Wörld") == "hello-world"

    def test_already_clean(self) -> None:
        assert slug("hello-world") == "hello-world"

    def test_multiple_spaces(self) -> None:
        assert slug("a   b   c") == "a-b-c"


class TestTruncate:
    def test_no_truncation(self) -> None:
        assert truncate("hello", 10) == "hello"

    def test_truncated(self) -> None:
        assert truncate("hello world", 8) == "hello..."

    def test_exact_length(self) -> None:
        assert truncate("hello", 5) == "hello"

    def test_custom_suffix(self) -> None:
        assert truncate("hello world", 8, suffix="~") == "hello w~"

    def test_very_short_max(self) -> None:
        assert truncate("hello", 2) == "he"
