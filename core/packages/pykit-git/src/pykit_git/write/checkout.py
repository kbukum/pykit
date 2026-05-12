"""Checker protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pykit_git.options import CheckoutOptions


@runtime_checkable
class Checker(Protocol):
    """Checkout operations."""

    def checkout(self, ref_name: str, opts: CheckoutOptions | None = None) -> None:
        """Checkout a branch, tag, or revision."""
        raise NotImplementedError

    def checkout_files(self, *paths: str) -> None:
        """Restore paths from HEAD."""
        raise NotImplementedError
