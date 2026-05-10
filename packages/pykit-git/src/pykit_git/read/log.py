"""LogReader protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pykit_git.options import LogOptions
from pykit_git.types import Commit, Oid


@runtime_checkable
class LogReader(Protocol):
    """Commit history operations."""

    def log(self, opts: LogOptions | None = None) -> list[Commit]:
        """Return commits from the repository history."""
        ...

    def merge_base(self, a: str, b: str) -> Oid:
        """Return the best common ancestor of two revisions."""
        ...

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        """Report whether one revision is an ancestor of another."""
        ...
