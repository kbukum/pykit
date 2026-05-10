"""Inspector protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pykit_git.options import DescribeOptions, GrepOptions
from pykit_git.types import GrepMatch, Oid


@runtime_checkable
class Inspector(Protocol):
    """Read-only revision inspection helpers."""

    def describe(self, opts: DescribeOptions | None = None) -> str:
        """Describe the current revision."""
        ...

    def rev_parse(self, revision: str) -> Oid:
        """Resolve a revision expression to an OID."""
        ...

    def grep(self, pattern: str, revision: str, opts: GrepOptions | None = None) -> list[GrepMatch]:
        """Search file contents at a revision."""
        ...

    def show(self, object: str) -> bytes:
        """Show a git object or revision spec."""
        ...
