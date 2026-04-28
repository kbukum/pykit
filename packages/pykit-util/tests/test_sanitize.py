"""Tests for pykit_util sanitize utilities."""

from pykit_util import is_safe_string, sanitize_env_value, sanitize_string


class TestSanitizeString:
    def test_trims_and_strips_control(self) -> None:
        assert sanitize_string("  hello\x00world  ") == "helloworld"

    def test_clean_string(self) -> None:
        assert sanitize_string("  clean  ") == "clean"

    def test_empty(self) -> None:
        assert sanitize_string("") == ""

    def test_unicode(self) -> None:
        assert sanitize_string("café ☕") == "café ☕"

    def test_emoji(self) -> None:
        assert sanitize_string("emoji 🎉") == "emoji 🎉"


class TestSanitizeEnvValue:
    def test_double_quotes(self) -> None:
        assert sanitize_env_value('"hello"') == "hello"

    def test_single_quotes(self) -> None:
        assert sanitize_env_value("'hello'") == "hello"

    def test_no_quotes(self) -> None:
        assert sanitize_env_value("no_quotes") == "no_quotes"

    def test_mismatched_quotes(self) -> None:
        assert sanitize_env_value("\"mismatched'") == "\"mismatched'"

    def test_whitespace(self) -> None:
        assert sanitize_env_value('  "spaced"  ') == "spaced"


class TestIsSafeString:
    def test_safe(self) -> None:
        assert is_safe_string("normal input") is True

    def test_sql_injection(self) -> None:
        assert is_safe_string("--; DROP TABLE users") is False

    def test_script_tag(self) -> None:
        assert is_safe_string("<script>alert(1)</script>") is False

    def test_path_traversal(self) -> None:
        assert is_safe_string("../../etc/passwd") is False

    def test_shell_injection(self) -> None:
        assert is_safe_string("$(rm -rf /)") is False
