"""TreeReader protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pykit_git.types import TreeEntry, TreeHash


@runtime_checkable
class TreeReader(Protocol):
    """Read access to git tree objects."""

    def tree_hash(self, revision: str, path: str) -> TreeHash:
        """Return the OID of the tree at the given revision and path."""
        ...

    def file_at(self, revision: str, path: str) -> bytes:
        """Return the content of a file at the given revision and path."""
        ...

    def list_entries(self, revision: str, path: str) -> list[TreeEntry]:
        """Return entries in a tree at the given revision and path."""
        ...
