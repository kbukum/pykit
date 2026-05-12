"""IndexManager protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pykit_git.types import StatusEntry


@runtime_checkable
class IndexManager(Protocol):
    """Index staging operations."""

    def stage(self, *paths: str) -> None:
        """Stage one or more paths."""
        raise NotImplementedError

    def unstage(self, *paths: str) -> None:
        """Unstage one or more paths."""
        raise NotImplementedError

    def staged_entries(self) -> list[StatusEntry]:
        """Return files staged in the index."""
        raise NotImplementedError
