"""Tests for pykit-authz."""

from __future__ import annotations

import grpc
import pytest

from pykit_authz import (
    Checker,
    CheckerFunc,
    MapChecker,
    PermissionDeniedError,
    match_any,
    match_pattern,
)

# --- match_pattern -----------------------------------------------------------


class TestMatchPattern:
    def test_exact_match(self) -> None:
        assert match_pattern("article:read", "article:read") is True

    def test_exact_no_match(self) -> None:
        assert match_pattern("article:read", "article:write") is False

    def test_universal_wildcard_star(self) -> None:
        assert match_pattern("*", "article:read") is True

    def test_universal_wildcard_star_star(self) -> None:
        assert match_pattern("*:*", "article:read") is True

    def test_resource_wildcard(self) -> None:
        assert match_pattern("article:*", "article:read") is True
        assert match_pattern("article:*", "article:write") is True

    def test_resource_wildcard_no_match(self) -> None:
        assert match_pattern("article:*", "user:read") is False

    def test_action_wildcard(self) -> None:
        assert match_pattern("*:read", "article:read") is True
        assert match_pattern("*:read", "user:read") is True

    def test_action_wildcard_no_match(self) -> None:
        assert match_pattern("*:read", "article:write") is False

    def test_plain_string_exact(self) -> None:
        assert match_pattern("admin", "admin") is True

    def test_plain_string_no_match(self) -> None:
        assert match_pattern("admin", "editor") is False

    def test_plain_wildcard(self) -> None:
        assert match_pattern("*", "anything") is True

    def test_format_mismatch(self) -> None:
        assert match_pattern("article:read", "admin") is False
        assert match_pattern("admin", "article:read") is False


# --- match_any ---------------------------------------------------------------


class TestMatchAny:
    def test_one_matches(self) -> None:
        assert match_any(["article:read", "article:write"], "article:read") is True

    def test_none_match(self) -> None:
        assert match_any(["article:read", "article:write"], "user:delete") is False

    def test_empty_patterns(self) -> None:
        assert match_any([], "article:read") is False

    def test_wildcard_in_list(self) -> None:
        assert match_any(["user:read", "*"], "anything:here") is True


# --- MapChecker --------------------------------------------------------------


class TestMapChecker:
    @pytest.fixture
    def checker(self) -> MapChecker:
        return MapChecker(
            {
                "admin": ["*"],
                "editor": ["article:read", "article:write"],
                "viewer": ["*:read"],
            }
        )

    def test_admin_wildcard(self, checker: MapChecker) -> None:
        assert checker.check("admin", "article:delete") is True
        assert checker.check("admin", "user:write") is True

    def test_editor_allowed(self, checker: MapChecker) -> None:
        assert checker.check("editor", "article:read") is True
        assert checker.check("editor", "article:write") is True

    def test_editor_denied(self, checker: MapChecker) -> None:
        assert checker.check("editor", "user:delete") is False

    def test_viewer_action_wildcard(self, checker: MapChecker) -> None:
        assert checker.check("viewer", "article:read") is True
        assert checker.check("viewer", "user:read") is True
        assert checker.check("viewer", "article:write") is False

    def test_unknown_role(self, checker: MapChecker) -> None:
        assert checker.check("ghost", "article:read") is False

    def test_add_role(self, checker: MapChecker) -> None:
        checker.add_role("moderator", ["comment:delete"])
        assert checker.check("moderator", "comment:delete") is True
        assert checker.check("moderator", "article:write") is False

    def test_remove_role(self, checker: MapChecker) -> None:
        checker.remove_role("editor")
        assert checker.check("editor", "article:read") is False

    def test_remove_nonexistent_role(self, checker: MapChecker) -> None:
        checker.remove_role("nonexistent")  # no error

    def test_satisfies_checker_protocol(self, checker: MapChecker) -> None:
        assert isinstance(checker, Checker)


# --- CheckerFunc -------------------------------------------------------------


class TestCheckerFunc:
    def test_wraps_callable(self) -> None:
        fn = CheckerFunc(lambda subj, perm, res: subj == "admin")
        assert fn.check("admin", "anything") is True
        assert fn.check("editor", "anything") is False

    def test_resource_forwarded(self) -> None:
        calls: list[tuple[str, str, str]] = []

        def spy(subj: str, perm: str, res: str) -> bool:
            calls.append((subj, perm, res))
            return True

        fn = CheckerFunc(spy)
        fn.check("admin", "article:read", "article-42")
        assert calls == [("admin", "article:read", "article-42")]

    def test_satisfies_checker_protocol(self) -> None:
        fn = CheckerFunc(lambda s, p, r: True)
        assert isinstance(fn, Checker)


# --- PermissionDeniedError ---------------------------------------------------


class TestPermissionDeniedError:
    def test_message(self) -> None:
        err = PermissionDeniedError("editor", "user:delete")
        assert "editor" in str(err)
        assert "user:delete" in str(err)

    def test_grpc_status(self) -> None:
        err = PermissionDeniedError("editor", "user:delete")
        assert err.grpc_status == grpc.StatusCode.PERMISSION_DENIED

    def test_details(self) -> None:
        err = PermissionDeniedError("viewer", "article:write")
        assert err.details == {"subject": "viewer", "permission": "article:write"}

    def test_is_app_error(self) -> None:
        from pykit_errors import AppError

        err = PermissionDeniedError("x", "y")
        assert isinstance(err, AppError)

    def test_raise_and_catch(self) -> None:
        with pytest.raises(PermissionDeniedError):
            raise PermissionDeniedError("guest", "admin:panel")
