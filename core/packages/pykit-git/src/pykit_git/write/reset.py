"""Resetter protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pykit_git.types import ResetMode


@runtime_checkable
class Resetter(Protocol):
    """Reset operations."""

    def reset(self, target: str, mode: ResetMode) -> None:
        """Reset repository state to a target revision."""
        raise NotImplementedError
