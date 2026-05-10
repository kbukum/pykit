"""Stasher protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pykit_git.types import Oid, StashEntry


@runtime_checkable
class Stasher(Protocol):
    """Stash operations."""

    def stash(self, message: str) -> Oid:
        """Create a stash entry."""
        ...

    def stash_push(self, message: str) -> Oid:
        """Create a stash entry."""
        ...

    def stash_pop(self, index: int = 0) -> None:
        """Pop a stash entry."""
        ...

    def stash_list(self) -> list[StashEntry]:
        """List available stash entries."""
        ...
