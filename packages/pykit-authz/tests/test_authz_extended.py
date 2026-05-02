"""Additional security-focused authz tests."""

from __future__ import annotations

from pykit_authz import ABACRule, AuthorizationEngine, AuthorizationRequest, Resource, RoleBinding, Subject


def _request(role: str, action: str, tenant: str = "acme") -> AuthorizationRequest:
    return AuthorizationRequest(
        subject=Subject("user-1", roles=(role,), attributes={"tenant": tenant}),
        action=action,
        resource=Resource("article", "article-1", attributes={"tenant": tenant}),
    )


class TestPrivilegeEscalation:
    def test_role_hierarchy_does_not_escalate_sideways(self) -> None:
        engine = AuthorizationEngine(
            roles=[
                RoleBinding("viewer", ("article:read",)),
                RoleBinding("editor", ("article:write",), inherits=("viewer",)),
                RoleBinding("billing-admin", ("billing:*",)),
            ]
        )

        assert engine.check(_request("viewer", "read")) is True
        assert engine.check(_request("viewer", "write")) is False
        assert (
            engine.check(
                AuthorizationRequest(Subject("user-1", roles=("editor",)), "delete", Resource("billing"))
            )
            is False
        )
        assert (
            engine.check(
                AuthorizationRequest(
                    Subject("user-1", roles=("billing-admin",)), "write", Resource("article")
                )
            )
            is False
        )

    def test_default_deny_when_no_policy_matches(self) -> None:
        engine = AuthorizationEngine(
            roles=[RoleBinding("viewer", ("article:read",))],
            rules=[
                ABACRule(
                    name="same-tenant",
                    actions=("read",),
                    resources=("article",),
                    subject_attributes={"tenant": "acme"},
                )
            ],
        )

        request = AuthorizationRequest(
            subject=Subject("user-1", roles=("viewer",), attributes={"tenant": "other"}),
            action="delete",
            resource=Resource("article", "article-1", attributes={"tenant": "acme"}),
        )
        assert engine.authorize(request).allowed is False
