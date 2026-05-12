"""CherryPicker protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pykit_git.options import CherryPickOptions
from pykit_git.types import Oid


@runtime_checkable
class CherryPicker(Protocol):
    """Cherry-pick operations."""

    def cherry_pick(self, commit: str, opts: CherryPickOptions | None = None) -> Oid:
        """Cherry-pick a commit."""
        ...

    def cherry_pick_continue(self) -> Oid:
        """Continue an in-progress cherry-pick."""
        ...

    def cherry_pick_abort(self) -> None:
        """Abort an in-progress cherry-pick."""
        ...
