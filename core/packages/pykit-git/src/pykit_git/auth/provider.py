"""Token provider protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pykit_git.auth.transport import Token


@runtime_checkable
class TokenProvider(Protocol):
    """Provides transport tokens for remotes."""

    def get_token(self, remote: str) -> Token | None:
        """Return a token for a remote, if one is available."""
        ...
