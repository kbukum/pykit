"""Embedded pygit2 backend."""

from pykit_git.embedded.repo import Backend, clone, discover, init, init_bare, open

__all__ = ["Backend", "clone", "discover", "init", "init_bare", "open"]
