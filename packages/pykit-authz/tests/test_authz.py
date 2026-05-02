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
    PermissionDeniedError,
    Resource,
    RoleBinding,
    Subject,
    match_any,
    match_pattern,
)

type _Attrs = dict[str, str | int | float | bool]


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
