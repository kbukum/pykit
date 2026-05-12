"""Repository protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from pykit_git.types import Oid, Reference


@runtime_checkable
class Repository(Protocol):
    """Core git repository operations."""

    @property
    def root(self) -> Path:
        """Absolute path to the repository root."""
        ...

    def head(self) -> Reference:
        """Return the reference that HEAD points to."""
        ...

    def resolve_ref(self, refname: str) -> Oid:
        """Resolve a ref name to an OID."""
        ...

    def is_dirty(self) -> bool:
        """Report whether the working tree has uncommitted changes."""
        ...
