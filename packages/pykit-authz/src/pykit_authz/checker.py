"""Authorization checker interfaces and implementations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from pykit_authz.matcher import match_any


@runtime_checkable
class Checker(Protocol):
    """Core authorization interface.

    *subject* is typically a role name, user ID, or group.
    *permission* is the required permission string (e.g. ``"article:write"``).
    *resource* is an optional resource identifier for fine-grained checks.
    """

    def check(self, subject: str, permission: str, resource: str = "") -> bool: ...


class CheckerFunc:
    """Adapter that wraps an ordinary callable as a :class:`Checker`."""

    def __init__(self, fn: Callable[[str, str, str], bool]) -> None:
        self._fn = fn

    def check(self, subject: str, permission: str, resource: str = "") -> bool:
        return self._fn(subject, permission, resource)


class MapChecker:
    """In-memory :class:`Checker` backed by a role → permission-patterns map.

    Supports wildcard matching via :func:`~pykit_authz.matcher.match_pattern`.

    Example::

        checker = MapChecker({
            "admin":  ["*"],
            "editor": ["article:read", "article:write"],
        })
        checker.check("admin", "article:delete")   # True
        checker.check("editor", "article:read")     # True
        checker.check("editor", "user:delete")      # False
    """

    def __init__(self, role_permissions: dict[str, list[str]]) -> None:
        self._permissions: dict[str, list[str]] = dict(role_permissions)

    def check(self, subject: str, permission: str, resource: str = "") -> bool:
        """Return ``True`` if *subject* (role) has a pattern matching *permission*."""
        patterns = self._permissions.get(subject)
        if patterns is None:
            return False
        return match_any(patterns, permission)

    def add_role(self, role: str, permissions: list[str]) -> None:
        """Add or replace permissions for *role*."""
        self._permissions[role] = list(permissions)

    def remove_role(self, role: str) -> None:
        """Remove *role* and its permissions. No-op if the role doesn't exist."""
        self._permissions.pop(role, None)
