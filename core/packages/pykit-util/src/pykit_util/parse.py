"""Parsing utilities — pure Python, zero dependencies."""

from __future__ import annotations

import re

_SIZE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(b|kb|mb|gb|tb|)\s*$", re.IGNORECASE)

_SIZE_MULTIPLIERS: dict[str, int] = {
    "": 1,
    "b": 1,
    "kb": 1024,
    "mb": 1024**2,
    "gb": 1024**3,
    "tb": 1024**4,
}

_TRUTHY = frozenset({"true", "yes", "1", "on", "t", "y"})
_FALSY = frozenset({"false", "no", "0", "off", "f", "n", ""})


def parse_size(s: str, default: int = 0) -> int:
    """Parse a human-readable size string (e.g. ``"10MB"``) into bytes."""
    m = _SIZE_RE.match(s)
    if not m:
        return default
    value = float(m.group(1))
    unit = m.group(2).lower()
    return int(value * _SIZE_MULTIPLIERS[unit])


def mask_secret(s: str, visible_prefix: int = 4) -> str:
    """Mask a secret, keeping the first *visible_prefix* characters visible.

    Example::

        >>> mask_secret("abcdefgh")
        'abcd***'
    """
    if len(s) <= visible_prefix:
        return "***"
    return s[:visible_prefix] + "***"


def parse_bool(s: str) -> bool:
    """Parse common boolean string representations.

    Raises ``ValueError`` for unrecognised inputs.
    """
    normalised = s.strip().lower()
    if normalised in _TRUTHY:
        return True
    if normalised in _FALSY:
        return False
    raise ValueError(f"cannot parse {s!r} as bool")
