"""pykit-authz — RBAC permission checking with wildcard pattern matching."""

from __future__ import annotations

from pykit_authz.checker import Checker, CheckerFunc, MapChecker
from pykit_authz.errors import PermissionDeniedError
from pykit_authz.matcher import match_any, match_pattern

__all__ = [
    "Checker",
    "CheckerFunc",
    "MapChecker",
    "PermissionDeniedError",
    "match_any",
    "match_pattern",
]
