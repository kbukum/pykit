"""Extended tests for pykit-authz — concurrency, edge cases, and security."""

from __future__ import annotations

import concurrent.futures
import threading

import pytest

from pykit_authz import (
    Checker,
    CheckerFunc,
    MapChecker,
    PermissionDeniedError,
    match_any,
    match_pattern,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Concurrent access
# ═══════════════════════════════════════════════════════════════════════════════


class TestConcurrentMapChecker:
    def test_concurrent_check_calls(self) -> None:
        checker = MapChecker(
            {
                "admin": ["*"],
                "editor": ["article:read", "article:write"],
                "viewer": ["*:read"],
            }
        )
        errors: list[str] = []

        def check_many(role: str, perm: str, expected: bool) -> None:
            for _ in range(100):
                result = checker.check(role, perm)
                if result != expected:
                    errors.append(f"{role}/{perm}: expected {expected}, got {result}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            pool.submit(check_many, "admin", "article:delete", True)
            pool.submit(check_many, "editor", "article:read", True)
            pool.submit(check_many, "viewer", "article:write", False)
            pool.submit(check_many, "ghost", "anything", False)

        assert errors == [], f"Concurrent errors: {errors}"

    def test_concurrent_add_and_remove_roles(self) -> None:
        checker = MapChecker({"base": ["base:read"]})
        barrier = threading.Barrier(4)

        def add_roles() -> None:
            barrier.wait()
            for i in range(50):
                checker.add_role(f"role_{i}", [f"perm:{i}"])

        def remove_roles() -> None:
            barrier.wait()
            for i in range(50):
                checker.remove_role(f"role_{i}")

        def read_checks() -> None:
            barrier.wait()
            for _ in range(50):
                checker.check("base", "base:read")

        threads = [
            threading.Thread(target=add_roles),
            threading.Thread(target=add_roles),
            threading.Thread(target=remove_roles),
            threading.Thread(target=read_checks),
        ]
        for th in threads:
            th.start()
        for th in threads:
            th.join(timeout=10)
        # No crash = success; dict operations in CPython are thread-safe
        # due to the GIL for basic ops


# ═══════════════════════════════════════════════════════════════════════════════
# MapChecker edge cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestMapCheckerEdgeCases:
    def test_empty_role_name(self) -> None:
        checker = MapChecker({"": ["article:read"]})
        assert checker.check("", "article:read") is True
        assert checker.check("admin", "article:read") is False

    def test_empty_permission_list(self) -> None:
        checker = MapChecker({"editor": []})
        assert checker.check("editor", "article:read") is False

    def test_duplicate_role_addition(self) -> None:
        checker = MapChecker({"editor": ["article:read"]})
        checker.add_role("editor", ["article:write"])
        # add_role replaces, so old permission should be gone
        assert checker.check("editor", "article:read") is False
        assert checker.check("editor", "article:write") is True

    def test_unicode_role_and_permission(self) -> None:
        checker = MapChecker({"管理者": ["記事:読む"]})
        assert checker.check("管理者", "記事:読む") is True
        assert checker.check("管理者", "記事:書く") is False

    def test_very_large_permission_set(self) -> None:
        roles = {f"role_{i}": [f"resource_{i}:read"] for i in range(1000)}
        checker = MapChecker(roles)
        assert checker.check("role_0", "resource_0:read") is True
        assert checker.check("role_999", "resource_999:read") is True
        assert checker.check("role_0", "resource_1:read") is False
        assert checker.check("nonexistent", "resource_0:read") is False


# ═══════════════════════════════════════════════════════════════════════════════
# match_pattern edge cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestMatchPatternExtended:
    def test_multiple_colons(self) -> None:
        # split(":", maxsplit=1) → "a" and "b:c"
        assert match_pattern("a:b:c", "a:b:c") is True
        assert match_pattern("a:*", "a:b:c") is True
        assert match_pattern("a:b", "a:b:c") is False

    def test_single_colon(self) -> None:
        assert match_pattern(":", ":") is True

    def test_whitespace_significance(self) -> None:
        assert match_pattern(" article:read", "article:read") is False
        assert match_pattern("article:read ", "article:read") is False

    def test_special_regex_characters(self) -> None:
        """Ensure no regex injection — these are plain string comparisons."""
        assert match_pattern("a.b:read", "a.b:read") is True
        assert match_pattern("a.b:read", "axb:read") is False
        assert match_pattern("[admin]:read", "[admin]:read") is True
        assert match_pattern("user+tag:write", "user+tag:write") is True

    def test_empty_both(self) -> None:
        assert match_pattern("", "") is True

    def test_empty_pattern_nonempty_required(self) -> None:
        assert match_pattern("", "article:read") is False

    def test_case_sensitive_patterns(self) -> None:
        assert match_pattern("Article:Read", "article:read") is False
        assert match_pattern("ADMIN", "admin") is False


# ═══════════════════════════════════════════════════════════════════════════════
# match_any edge cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestMatchAnyExtended:
    def test_large_pattern_list(self) -> None:
        patterns = [f"resource_{i}:read" for i in range(1000)]
        assert match_any(patterns, "resource_999:read") is True
        assert match_any(patterns, "resource_0:write") is False


# ═══════════════════════════════════════════════════════════════════════════════
# CheckerFunc extended
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckerFuncExtended:
    def test_exception_raising_callable(self) -> None:
        def exploding(subj: str, perm: str, res: str) -> bool:
            raise ValueError("boom")

        fn = CheckerFunc(exploding)
        with pytest.raises(ValueError, match="boom"):
            fn.check("admin", "anything")

    def test_resource_default_empty(self) -> None:
        """When resource is not passed, it defaults to empty string."""
        received: list[tuple[str, str, str]] = []

        def spy(subj: str, perm: str, res: str) -> bool:
            received.append((subj, perm, res))
            return True

        fn = CheckerFunc(spy)
        fn.check("admin", "read")
        assert received == [("admin", "read", "")]

    def test_protocol_compliance(self) -> None:
        fn = CheckerFunc(lambda s, p, r: True)
        assert isinstance(fn, Checker)


# ═══════════════════════════════════════════════════════════════════════════════
# PermissionDeniedError extended
# ═══════════════════════════════════════════════════════════════════════════════


class TestPermissionDeniedErrorExtended:
    def test_details_preserved(self) -> None:
        err = PermissionDeniedError("viewer", "admin:panel")
        assert err.details["subject"] == "viewer"
        assert err.details["permission"] == "admin:panel"

    def test_unicode_in_error(self) -> None:
        err = PermissionDeniedError("管理者", "記事:削除")
        assert "管理者" in str(err)
        assert "記事:削除" in str(err)

    def test_empty_strings(self) -> None:
        err = PermissionDeniedError("", "")
        assert isinstance(err, PermissionDeniedError)


# ═══════════════════════════════════════════════════════════════════════════════
# Security-focused tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSecurity:
    def test_default_deny_empty_checker(self) -> None:
        checker = MapChecker({})
        assert checker.check("admin", "article:read") is False

    def test_default_deny_unknown_subject(self) -> None:
        checker = MapChecker({"admin": ["*"]})
        assert checker.check("unknown", "article:read") is False

    def test_wildcard_does_not_cross_subjects(self) -> None:
        checker = MapChecker({"admin": ["*"], "viewer": ["*:read"]})
        assert checker.check("viewer", "article:write") is False

    def test_case_sensitive_subject_lookup(self) -> None:
        checker = MapChecker({"admin": ["*"]})
        assert checker.check("Admin", "article:read") is False
        assert checker.check("ADMIN", "article:read") is False

    def test_wildcard_in_requested_permission_no_auto_grant(self) -> None:
        """A user requesting '*:*' should NOT match specific patterns."""
        checker = MapChecker({"viewer": ["article:read"]})
        assert checker.check("viewer", "*:*") is False
        assert checker.check("viewer", "*") is False

    def test_resource_parameter_ignored(self) -> None:
        """MapChecker currently ignores the resource parameter."""
        checker = MapChecker({"editor": ["article:write"]})
        # resource doesn't affect the result
        assert checker.check("editor", "article:write", "article-123") is True
        assert checker.check("editor", "article:write", "DIFFERENT") is True

    def test_removed_role_denied(self) -> None:
        checker = MapChecker({"temp": ["article:read"]})
        assert checker.check("temp", "article:read") is True
        checker.remove_role("temp")
        assert checker.check("temp", "article:read") is False
