"""Executor protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Executor(Protocol):
    """Executes git CLI commands synchronously."""

    def exec(self, *args: str) -> bytes:
        """Run a command and return raw stdout bytes."""
        ...
