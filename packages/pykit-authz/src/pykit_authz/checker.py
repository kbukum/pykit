"""RBAC + ABAC authorization engine with default-deny semantics."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

from pykit_authz.errors import PermissionDeniedError
from pykit_authz.matcher import match_any

type AttributeValue = str | int | float | bool
type Attributes = Mapping[str, AttributeValue]
type AttributeSource = Literal["subject", "resource", "context"]
type ConditionOperator = Literal["equals", "not_equals", "one_of"]


@dataclass(frozen=True, slots=True)
class Subject:
    """Authenticated subject."""

    subject_id: str
    roles: tuple[str, ...] = ()
    attributes: dict[str, AttributeValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Resource:
    """Authorization target."""

    resource_type: str
    resource_id: str = ""
    attributes: dict[str, AttributeValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    """Authorization request."""

    subject: Subject
    action: str
    resource: Resource

    @property
    def permission(self) -> str:
        """Return the canonical ``resource:action`` permission."""

        return f"{self.resource.resource_type}:{self.action}"


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    """Authorization decision."""

    allowed: bool
    reason: str
    matched_policies: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Condition:
    """Structured ABAC condition matching gokit/rskit canonical shape.

    Reads an attribute from *source* at *key* and applies *operator* against
    *values*.  Optionally compares against another attribute via *compare_source*
    and *compare_key* instead of literal *values*.
    """

    source: AttributeSource
    key: str
    operator: ConditionOperator = "equals"
    values: tuple[AttributeValue, ...] = ()
    compare_source: AttributeSource | None = None
    compare_key: str | None = None

    def matches(self, request: AuthorizationRequest) -> bool:
        """Return ``True`` when the condition is satisfied by *request*."""

        actual = _attribute_value(request, self.source, self.key)
        if actual is None:
            return False

        if self.compare_source is not None and self.compare_key is not None:
            other = _attribute_value(request, self.compare_source, self.compare_key)
            if other is None:
                return False
            expected: tuple[AttributeValue, ...] = (other,)
        else:
            expected = self.values

        if self.operator == "equals":
            return len(expected) == 1 and actual == expected[0]
        if self.operator == "not_equals":
            return len(expected) == 1 and actual != expected[0]
        if self.operator == "one_of":
            return actual in expected
        return False


def _attribute_value(
    request: AuthorizationRequest, source: AttributeSource, key: str
) -> AttributeValue | None:
    if source == "subject":
        if key == "id":
            return request.subject.subject_id or None
        return request.subject.attributes.get(key)
    if source == "resource":
        if key == "id":
            return request.resource.resource_id or None
        if key == "type":
            return request.resource.resource_type or None
        return request.resource.attributes.get(key)
    if source == "context":
        return None  # context attributes not exposed on AuthorizationRequest directly
    return None


@dataclass(frozen=True, slots=True)
class RoleBinding:
    """RBAC role definition with optional inheritance."""

    name: str
    permissions: tuple[str, ...]
    inherits: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ABACRule:
    """ABAC rule.

    Attribute matching is specified via *subject_attributes* / *resource_attributes*
    convenience dicts (equality only) or via the *conditions* tuple for full typed
    operator support (equals / not_equals / one_of) and cross-field comparisons.
    Both are evaluated; all must match.
    """

    name: str
    effect: Literal["allow", "deny"] = "allow"
    actions: tuple[str, ...] = ("*",)
    resources: tuple[str, ...] = ("*",)
    subject_attributes: dict[str, AttributeValue] = field(default_factory=dict)
    resource_attributes: dict[str, AttributeValue] = field(default_factory=dict)
    conditions: tuple[Condition, ...] = ()

    def matches(self, request: AuthorizationRequest) -> bool:
        """Return ``True`` when this rule matches *request*."""

        if not match_any(list(self.actions), request.action):
            return False
        if not match_any(list(self.resources), request.resource.resource_type):
            return False
        if not _attributes_match(self.subject_attributes, request.subject.attributes):
            return False
        if not _attributes_match(self.resource_attributes, request.resource.attributes):
            return False
        return all(cond.matches(request) for cond in self.conditions)


def _attributes_match(expected: Attributes, actual: Attributes) -> bool:
    return all(actual.get(key) == value for key, value in expected.items())


@runtime_checkable
class Checker(Protocol):
    """Authorization checker protocol."""

    def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision: ...

    def check(self, request: AuthorizationRequest) -> bool: ...


class CheckerFunc:
    """Adapt a callable into a :class:`Checker`."""

    def __init__(self, fn: Callable[[AuthorizationRequest], AuthorizationDecision | bool]) -> None:
        self._fn = fn

    def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision:
        result = self._fn(request)
        if isinstance(result, AuthorizationDecision):
            return result
        reason = "callable_allow" if result else "callable_deny"
        return AuthorizationDecision(allowed=result, reason=reason)

    def check(self, request: AuthorizationRequest) -> bool:
        return self.authorize(request).allowed


class AuthorizationEngine:
    """Canonical RBAC + ABAC authorizer with default-deny semantics."""

    def __init__(
        self,
        roles: Sequence[RoleBinding] = (),
        rules: Sequence[ABACRule] = (),
    ) -> None:
        self._roles = {role.name: role for role in roles}
        self._rules = tuple(rules)

    def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision:
        """Authorize *request*."""

        deny_matches = tuple(
            rule.name for rule in self._rules if rule.effect == "deny" and rule.matches(request)
        )
        if deny_matches:
            return AuthorizationDecision(False, "explicit_deny", deny_matches)

        allow_matches: list[str] = []

        # RBAC role grants checked before ABAC allow policies (canonical cross-kit order).
        for role_name in self._expand_roles(request.subject.roles):
            role = self._roles.get(role_name)
            if role and match_any(list(role.permissions), request.permission):
                allow_matches.append(f"rbac:{role.name}")

        for rule in self._rules:
            if rule.effect == "allow" and rule.matches(request):
                allow_matches.append(rule.name)

        if allow_matches:
            return AuthorizationDecision(True, "allow", tuple(allow_matches))
        return AuthorizationDecision(False, "default_deny")

    def check(self, request: AuthorizationRequest) -> bool:
        """Return ``True`` when *request* is allowed."""

        return self.authorize(request).allowed

    def require(self, request: AuthorizationRequest) -> None:
        """Raise when *request* is not allowed."""

        decision = self.authorize(request)
        if not decision.allowed:
            raise PermissionDeniedError(request.subject.subject_id, request.permission, decision.reason)

    def _expand_roles(self, roles: Sequence[str]) -> tuple[str, ...]:
        resolved: list[str] = []
        seen: set[str] = set()

        def visit(role_name: str) -> None:
            if role_name in seen:
                return
            seen.add(role_name)
            role = self._roles.get(role_name)
            if role is None:
                resolved.append(role_name)
                return
            for parent in role.inherits:
                visit(parent)
            resolved.append(role_name)

        for role_name in roles:
            visit(role_name)
        return tuple(resolved)
