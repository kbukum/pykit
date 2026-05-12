"""Rebaser protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pykit_git.options import RebaseOptions
from pykit_git.types import RebaseResult


@runtime_checkable
class Rebaser(Protocol):
    """Rebase operations."""

    def rebase(self, onto: str, opts: RebaseOptions | None = None) -> RebaseResult:
        """Rebase the current branch onto another revision."""
        raise NotImplementedError

    def abort_rebase(self) -> None:
        """Abort an in-progress rebase."""
        raise NotImplementedError

    def continue_rebase(self) -> RebaseResult:
        """Continue an in-progress rebase."""
        raise NotImplementedError
