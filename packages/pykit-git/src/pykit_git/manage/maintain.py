"""Maintainer protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pykit_git.options import CleanOptions


@runtime_checkable
class Maintainer(Protocol):
    """Repository maintenance operations."""

    def gc(self) -> None:
        """Run repository garbage collection."""
        ...

    def prune(self) -> None:
        """Prune unreachable objects."""
        ...

    def fsck(self) -> None:
        """Check repository integrity."""
        ...

    def clean(self, opts: CleanOptions | None = None) -> list[str]:
        """Clean untracked files and return removed paths."""
        ...
