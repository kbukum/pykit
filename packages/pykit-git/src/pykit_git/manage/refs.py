"""RefManager protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pykit_git.types import Branch, BranchFilter, Tag


@runtime_checkable
class RefManager(Protocol):
    """Branch and tag operations."""

    def list_branches(self, filter: BranchFilter = BranchFilter.LOCAL) -> list[Branch]:
        """Return repository branches."""
        ...

    def list_tags(self) -> list[Tag]:
        """Return repository tags."""
        ...

    def create_branch(self, name: str, target: str) -> None:
        """Create a branch at the given target."""
        ...

    def delete_branch(self, name: str) -> None:
        """Delete a local branch."""
        ...

    def create_tag(self, name: str, target: str, message: str) -> None:
        """Create a tag. Creates an annotated tag when message is non-empty, lightweight otherwise."""
        ...

    def delete_tag(self, name: str) -> None:
        """Delete a tag."""
        ...
