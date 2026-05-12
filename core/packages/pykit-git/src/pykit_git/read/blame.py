"""Blamer protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pykit_git.options import BlameOptions
from pykit_git.types import BlameLine


@runtime_checkable
class Blamer(Protocol):
    """Line attribution operations."""

    def blame(self, revision: str, path: str, opts: BlameOptions | None = None) -> list[BlameLine]:
        """Return line-level attribution for a file."""
        ...
