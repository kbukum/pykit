"""Differ protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pykit_git.types import DiffEntry, DiffStats, StatusEntry


@runtime_checkable
class Differ(Protocol):
    """Diff and status operations."""

    def diff(self, from_ref: str, to_ref: str) -> list[DiffEntry]:
        """Return file changes between two refs."""
        ...

    def diff_stats(self, from_ref: str, to_ref: str) -> DiffStats:
        """Return aggregated statistics for changes between two refs."""
        ...

    def status(self) -> list[StatusEntry]:
        """Return the working tree status."""
        ...
