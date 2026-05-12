"""Committer protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pykit_git.options import CommitOptions
from pykit_git.types import Oid


@runtime_checkable
class Committer(Protocol):
    """Commit creation operations."""

    def commit(self, message: str, opts: CommitOptions | None = None) -> Oid:
        """Create a commit from the current index."""
        ...
