"""Tests for canonical RBAC + ABAC authz."""

from __future__ import annotations

import grpc
import pytest

from pykit_authz import (
    ABACRule,
    AuthorizationEngine,
    AuthorizationRequest,
    Checker,
    CheckerFunc,
    Condition,
    PermissionDeniedError,
    Resource,
    RoleBinding,
    Subject,
    match_any,
    match_pattern,
)

_Attrs = dict[str, str | int | float | bool]


def _request(
    *,
    roles: tuple[str, ...] = (),
    action: str = "read",
    resource_type: str = "article",
    subject_attrs: _Attrs | None = None,
    resource_attrs: _Attrs | None = None,
) -> AuthorizationRequest:
    return AuthorizationRequest(
        subject=Subject("user-1", roles=roles, attributes=subject_attrs or {}),
        action=action,
        resource=Resource(resource_type, "resource-1", attributes=resource_attrs or {}),
    )


class TestMatcherHelpers:
    def test_match_pattern(self) -> None:
        assert match_pattern("article:*", "article:read") is True
        assert match_pattern("*:read", "article:read") is True
        assert match_pattern("article:write", "article:read") is False

    def test_match_any(self) -> None:
        assert match_any(["article:read", "article:write"], "article:read") is True
        assert match_any([], "article:read") is False


class TestAuthorizationEngine:
    @pytest.fixture
    def engine(self) -> AuthorizationEngine:
        return AuthorizationEngine(
            roles=[
                RoleBinding("viewer", ("article:read",)),
                RoleBinding("editor", ("article:write",), inherits=("viewer",)),
                RoleBinding("admin", ("*",)),
            ],
            rules=[
                ABACRule(
                    name="tenant-allow",
                    actions=("read",),
                    resources=("article",),
                    subject_attributes={"tenant": "acme"},
                    resource_attributes={"tenant": "acme"},
                ),
                ABACRule(
                    name="suspended-deny",
                    effect="deny",
                    actions=("*",),
                    resources=("*",),
                    subject_attributes={"suspended": True},
                ),
            ],
        )

    def test_rbac_inheritance(self, engine: AuthorizationEngine) -> None:
        assert engine.check(_request(roles=("editor",), action="read")) is True
        assert engine.check(_request(roles=("editor",), action="write")) is True
        assert engine.check(_request(roles=("viewer",), action="write")) is False

    def test_default_deny(self, engine: AuthorizationEngine) -> None:
        decision = engine.authorize(_request(roles=("ghost",), action="delete"))
        assert decision.allowed is False
        assert decision.reason == "default_deny"

    def test_abac_allow(self, engine: AuthorizationEngine) -> None:
        decision = engine.authorize(
            _request(
                roles=(),
                action="read",
                subject_attrs={"tenant": "acme"},
                resource_attrs={"tenant": "acme"},
            )
        )
        assert decision.allowed is True
        assert "tenant-allow" in decision.matched_policies

    def test_abac_deny_overrides_rbac(self, engine: AuthorizationEngine) -> None:
        decision = engine.authorize(
            _request(
                roles=("admin",),
                action="delete",
                subject_attrs={"suspended": True},
            )
        )
        assert decision.allowed is False
        assert decision.reason == "explicit_deny"

    def test_require_raises_permission_denied(self, engine: AuthorizationEngine) -> None:
        with pytest.raises(PermissionDeniedError) as exc_info:
            engine.require(_request(roles=("viewer",), action="write"))
        assert exc_info.value.to_grpc_status() == grpc.StatusCode.PERMISSION_DENIED
        assert exc_info.value.details["reason"] == "default_deny"


class TestCheckerFunc:
    def test_checker_func_supports_protocol(self) -> None:
        checker = CheckerFunc(lambda request: request.action == "read")
        assert isinstance(checker, Checker)
        assert checker.check(_request(action="read")) is True
        assert checker.check(_request(action="write")) is False


class TestConditions:
    def test_condition_equals_not_equals_one_of_and_compare(self) -> None:
        req = AuthorizationRequest(
            subject=Subject("user-1", attributes={"tenant": "acme", "tier": "gold"}),
            action="read",
            resource=Resource("article", "res-1", attributes={"tenant": "acme", "state": "draft"}),
        )
        assert Condition("subject", "tenant", values=("acme",)).matches(req)
        assert Condition("resource", "state", operator="not_equals", values=("published",)).matches(req)
        assert Condition("subject", "tier", operator="one_of", values=("silver", "gold")).matches(req)
        assert Condition("subject", "tenant", compare_source="resource", compare_key="tenant").matches(req)
        assert Condition("subject", "missing", values=("x",)).matches(req) is False
        assert Condition("context", "missing", values=("x",)).matches(req) is False
        assert Condition("resource", "type", values=("article",)).matches(req)
        assert Condition("resource", "id", values=("res-1",)).matches(req)
        assert Condition("subject", "id", values=("user-1",)).matches(req)

    def test_rule_conditions_must_all_match(self) -> None:
        req = _request(subject_attrs={"tenant": "acme"}, resource_attrs={"tenant": "acme"})
        rule = ABACRule(
            name="same-tenant",
            actions=("read",),
            resources=("article",),
            conditions=(Condition("subject", "tenant", compare_source="resource", compare_key="tenant"),),
        )
        assert rule.matches(req)
