"""Merger protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pykit_git.options import MergeOptions
from pykit_git.types import MergeResult


@runtime_checkable
class Merger(Protocol):
    """Merge operations."""

    def merge(self, branch: str, opts: MergeOptions | None = None) -> MergeResult:
        """Merge a branch into the current HEAD."""
        raise NotImplementedError

    def abort_merge(self) -> None:
        """Abort an in-progress merge."""
        raise NotImplementedError
