"""Tests for slash commands."""

from __future__ import annotations

from pykit_agent.command import Command, CommandRegistry, register_builtins


class TestCommandRegistry:
    """CommandRegistry registration and lookup."""

    def test_register_and_get(self) -> None:
        reg = CommandRegistry()
        cmd = Command(name="test", description="A test command")
        reg.register(cmd)
        assert reg.get("test") is cmd

    def test_get_missing(self) -> None:
        reg = CommandRegistry()
        assert reg.get("nope") is None

    def test_list_sorted(self) -> None:
        reg = CommandRegistry()
        reg.register(Command(name="zzz", description="last"))
        reg.register(Command(name="aaa", description="first"))
        names = [c.name for c in reg.list()]
        assert names == ["aaa", "zzz"]

    def test_overwrite(self) -> None:
        reg = CommandRegistry()
        reg.register(Command(name="x", description="old"))
        reg.register(Command(name="x", description="new"))
        assert reg.get("x") is not None
        assert reg.get("x").description == "new"


class TestIsCommand:
    """CommandRegistry.is_command detection."""

    def test_valid_command(self) -> None:
        reg = CommandRegistry()
        reg.register(Command(name="help", description="h"))
        assert reg.is_command("/help") is True

    def test_with_args(self) -> None:
        reg = CommandRegistry()
        reg.register(Command(name="model", description="m"))
        assert reg.is_command("/model gpt-4") is True

    def test_unknown_command(self) -> None:
        reg = CommandRegistry()
        reg.register(Command(name="help", description="h"))
        assert reg.is_command("/unknown") is False

    def test_not_a_command(self) -> None:
        reg = CommandRegistry()
        assert reg.is_command("hello world") is False

    def test_empty_string(self) -> None:
        reg = CommandRegistry()
        assert reg.is_command("") is False

    def test_whitespace_prefix(self) -> None:
        reg = CommandRegistry()
        reg.register(Command(name="help", description="h"))
        assert reg.is_command("  /help") is True


class TestParseCommand:
    """CommandRegistry.parse_command parsing."""

    def test_simple_command(self) -> None:
        reg = CommandRegistry()
        reg.register(Command(name="clear", description="c"))
        result = reg.parse_command("/clear")
        assert result == ("clear", "")

    def test_command_with_args(self) -> None:
        reg = CommandRegistry()
        reg.register(Command(name="model", description="m"))
        result = reg.parse_command("/model gpt-4-turbo")
        assert result == ("model", "gpt-4-turbo")

    def test_unknown_returns_none(self) -> None:
        reg = CommandRegistry()
        assert reg.parse_command("/nope") is None

    def test_no_slash_returns_none(self) -> None:
        reg = CommandRegistry()
        assert reg.parse_command("just text") is None


class TestExecute:
    """CommandRegistry.execute integration."""

    def test_execute_with_handler(self) -> None:
        reg = CommandRegistry()
        reg.register(Command(name="echo", description="Echo", handler=lambda args: f"echo: {args}"))
        assert reg.execute("/echo hello") == "echo: hello"

    def test_execute_no_handler(self) -> None:
        reg = CommandRegistry()
        reg.register(Command(name="noop", description="No handler"))
        result = reg.execute("/noop")
        assert "no handler" in result

    def test_execute_unknown(self) -> None:
        reg = CommandRegistry()
        result = reg.execute("/unknown")
        assert "Unknown command" in result


class TestBuiltins:
    """register_builtins installs /help, /clear, /model, /compact."""

    def test_builtins_registered(self) -> None:
        reg = CommandRegistry()
        register_builtins(reg)
        names = {c.name for c in reg.list()}
        assert {"help", "clear", "model", "compact"} <= names

    def test_help_lists_commands(self) -> None:
        reg = CommandRegistry()
        register_builtins(reg)
        output = reg.execute("/help")
        assert "/help" in output
        assert "/clear" in output
        assert "/model" in output
        assert "/compact" in output

    def test_clear_handler(self) -> None:
        reg = CommandRegistry()
        register_builtins(reg)
        assert "cleared" in reg.execute("/clear")

    def test_model_handler_with_arg(self) -> None:
        reg = CommandRegistry()
        register_builtins(reg)
        result = reg.execute("/model gpt-4")
        assert "gpt-4" in result

    def test_model_handler_no_arg(self) -> None:
        reg = CommandRegistry()
        register_builtins(reg)
        result = reg.execute("/model")
        assert "Usage" in result

    def test_compact_handler(self) -> None:
        reg = CommandRegistry()
        register_builtins(reg)
        assert "compacted" in reg.execute("/compact")
