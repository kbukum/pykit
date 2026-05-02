"""pykit-authz — RBAC + ABAC authorization with default-deny semantics."""

from __future__ import annotations

from pykit_authz.checker import (
    ABACRule,
    AuthorizationDecision,
    AuthorizationEngine,
    AuthorizationRequest,
    Checker,
    CheckerFunc,
    Condition,
    Resource,
    RoleBinding,
    Subject,
)
from pykit_authz.errors import PermissionDeniedError
from pykit_authz.matcher import match_any, match_pattern

__all__ = [
    "ABACRule",
    "AuthorizationDecision",
    "AuthorizationEngine",
    "AuthorizationRequest",
    "Checker",
    "CheckerFunc",
    "Condition",
    "PermissionDeniedError",
    "Resource",
    "RoleBinding",
    "Subject",
    "match_any",
    "match_pattern",
]
