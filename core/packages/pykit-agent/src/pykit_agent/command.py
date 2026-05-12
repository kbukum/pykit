"""Slash commands — registry and built-in commands."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class Command:
    """A slash command definition."""

    name: str
    description: str
    usage: str = ""
    handler: Callable[[str], str] | None = None


class CommandRegistry:
    """Registry of slash commands keyed by ``/name``."""

    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}

    def register(self, cmd: Command) -> None:
        """Register a command (overwrites if already present)."""
        self._commands[cmd.name] = cmd

    def get(self, name: str) -> Command | None:
        """Return the command for *name*, or ``None``."""
        return self._commands.get(name)

    def list(self) -> list[Command]:
        """Return all registered commands sorted by name."""
        return sorted(self._commands.values(), key=lambda c: c.name)

    def is_command(self, input_text: str) -> bool:
        """Return ``True`` if *input_text* starts with a known ``/command``."""
        parsed = self.parse_command(input_text)
        return parsed is not None

    def parse_command(self, input_text: str) -> tuple[str, str] | None:
        """Parse ``/command args`` into ``(name, args)`` or ``None``.

        Returns ``None`` when *input_text* is not a recognised command.
        """
        stripped = input_text.strip()
        if not stripped.startswith("/"):
            return None

        parts = stripped.split(maxsplit=1)
        name = parts[0][1:]  # strip leading '/'
        args = parts[1] if len(parts) > 1 else ""

        if name not in self._commands:
            return None
        return name, args

    def execute(self, input_text: str) -> str:
        """Parse and execute a slash command, returning the output string.

        Returns an error message when the command is unknown or has no handler.
        """
        parsed = self.parse_command(input_text)
        if parsed is None:
            return f"Unknown command: {input_text.strip().split()[0]}"
        name, args = parsed
        cmd = self._commands[name]
        if cmd.handler is None:
            return f"/{name}: no handler registered"
        return cmd.handler(args)


# ---------------------------------------------------------------------------
# Built-in commands
# ---------------------------------------------------------------------------


def _help_handler(registry: CommandRegistry) -> Callable[[str], str]:
    """Build a /help handler that lists all commands in *registry*."""

    def _handler(args: str) -> str:
        lines = ["Available commands:"]
        for cmd in registry.list():
            usage = f"  {cmd.usage}" if cmd.usage else ""
            lines.append(f"  /{cmd.name}{usage} — {cmd.description}")
        return "\n".join(lines)

    return _handler


def _clear_handler(args: str) -> str:
    return "[conversation cleared]"


def _model_handler(args: str) -> str:
    if not args.strip():
        return "Usage: /model <model-name>"
    return f"[model switched to {args.strip()}]"


def _compact_handler(args: str) -> str:
    return "[context compacted]"


_BUILTINS: list[tuple[str, str, str, Callable[[str], str] | None]] = [
    ("help", "Show available commands", "", None),  # wired up in register_builtins
    ("clear", "Clear conversation history", "", _clear_handler),
    ("model", "Switch the active model", "<model-name>", _model_handler),
    ("compact", "Compact the conversation context", "", _compact_handler),
]


def register_builtins(registry: CommandRegistry) -> None:
    """Register the standard built-in slash commands on *registry*."""
    for name, desc, usage, handler in _BUILTINS:
        registry.register(Command(name=name, description=desc, usage=usage, handler=handler))
    # Wire up /help after all builtins are registered
    help_cmd = registry.get("help")
    if help_cmd is not None:
        help_cmd.handler = _help_handler(registry)
