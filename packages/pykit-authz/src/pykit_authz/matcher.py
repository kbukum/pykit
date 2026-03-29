"""Wildcard permission pattern matching."""

from __future__ import annotations


def _match_wildcard(pattern: str, value: str) -> bool:
    """Compare two strings where ``*`` matches anything."""
    return pattern == "*" or pattern == value


def match_pattern(pattern: str, permission: str) -> bool:
    """Check if a permission *pattern* matches a required *permission*.

    Supports ``resource:action`` format with wildcards:

    - ``*`` or ``*:*`` matches everything
    - ``article:*`` matches ``article:read``, ``article:write``, etc.
    - ``*:read`` matches ``article:read``, ``user:read``, etc.
    - ``article:read`` matches only ``article:read``

    Both *pattern* and *permission* use ``:`` as the separator.
    If either side does not contain ``:``, they are compared as plain
    strings with wildcard support.
    """
    if pattern == permission or pattern == "*" or pattern == "*:*":
        return True

    pat_parts = pattern.split(":", maxsplit=1)
    req_parts = permission.split(":", maxsplit=1)

    if len(pat_parts) != len(req_parts):
        return _match_wildcard(pattern, permission)

    if len(pat_parts) == 1:
        return _match_wildcard(pattern, permission)

    return _match_wildcard(pat_parts[0], req_parts[0]) and _match_wildcard(pat_parts[1], req_parts[1])


def match_any(patterns: list[str], permission: str) -> bool:
    """Return ``True`` if **any** of *patterns* match the required *permission*."""
    return any(match_pattern(p, permission) for p in patterns)
