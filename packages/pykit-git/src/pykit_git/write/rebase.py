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
        ...

    def abort_rebase(self) -> None:
        """Abort an in-progress rebase."""
        ...

    def continue_rebase(self) -> RebaseResult:
        """Continue an in-progress rebase."""
        ...

    def rebase_abort(self) -> None:
        """Abort an in-progress rebase."""
        ...

    def rebase_continue(self) -> RebaseResult:
        """Continue an in-progress rebase."""
        ...
