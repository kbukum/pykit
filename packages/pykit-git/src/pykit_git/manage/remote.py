"""RemoteManager protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pykit_git.options import FetchOptions, PushOptions
from pykit_git.types import Remote


@runtime_checkable
class RemoteManager(Protocol):
    """Remote repository operations."""

    def list_remotes(self) -> list[Remote]:
        """Return configured remotes."""
        ...

    def fetch(self, remote: str, opts: FetchOptions | None = None) -> None:
        """Fetch refs from a remote."""
        ...

    def push(self, remote: str, opts: PushOptions | None = None) -> None:
        """Push refs to a remote."""
        ...

    def tracking_branch(self, branch: str) -> str:
        """Return the upstream branch tracked by a local branch."""
        ...
