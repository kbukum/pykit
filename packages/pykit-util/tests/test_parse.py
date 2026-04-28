"""Tests for pykit_util parse utilities."""

import pytest

from pykit_util import mask_secret, parse_bool, parse_size


class TestParseSize:
    def test_megabytes(self) -> None:
        assert parse_size("10MB") == 10 * 1024 * 1024

    def test_kilobytes(self) -> None:
        assert parse_size("512KB") == 512 * 1024

    def test_gigabytes(self) -> None:
        assert parse_size("2GB") == 2 * 1024 * 1024 * 1024

    def test_plain_number(self) -> None:
        assert parse_size("1024") == 1024

    def test_case_insensitive(self) -> None:
        assert parse_size("10mb") == 10 * 1024 * 1024

    def test_with_whitespace(self) -> None:
        assert parse_size("  10MB  ") == 10 * 1024 * 1024

    def test_invalid_returns_default(self) -> None:
        assert parse_size("invalid", default=99) == 99

    def test_empty_returns_default(self) -> None:
        assert parse_size("", default=42) == 42


class TestMaskSecret:
    def test_basic(self) -> None:
        assert mask_secret("abcdefgh") == "abcd***"

    def test_short_string(self) -> None:
        assert mask_secret("abc", visible_prefix=10) == "***"

    def test_empty(self) -> None:
        assert mask_secret("") == "***"

    def test_custom_prefix(self) -> None:
        assert mask_secret("abcdef", visible_prefix=3) == "abc***"


class TestParseBool:
    @pytest.mark.parametrize("value", ["true", "True", "TRUE", "yes", "1", "on", "t", "y"])
    def test_truthy(self, value: str) -> None:
        assert parse_bool(value) is True

    @pytest.mark.parametrize("value", ["false", "False", "FALSE", "no", "0", "off", "f", "n", ""])
    def test_falsy(self, value: str) -> None:
        assert parse_bool(value) is False

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot parse"):
            parse_bool("maybe")
