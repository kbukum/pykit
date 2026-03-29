"""Tests for pykit_version."""

from __future__ import annotations

import subprocess
from dataclasses import FrozenInstanceError
from unittest.mock import patch

import pytest

from pykit_version import VersionInfo, get_full_version, get_short_version, get_version_info


class TestVersionInfoDataclass:
    """VersionInfo must be a frozen dataclass."""

    def test_frozen(self) -> None:
        info = VersionInfo(
            version="1.0.0",
            git_commit="abc1234",
            git_branch="main",
            build_time="2024-01-01T00:00:00Z",
            python_version="3.13.0",
            is_release=True,
            is_dirty=False,
        )
        with pytest.raises(FrozenInstanceError):
            info.version = "2.0.0"  # type: ignore[misc]

    def test_fields(self) -> None:
        info = VersionInfo(
            version="0.1.0",
            git_commit="",
            git_branch="",
            build_time="",
            python_version="3.13.0",
            is_release=False,
            is_dirty=False,
        )
        assert info.version == "0.1.0"
        assert info.python_version == "3.13.0"


class TestGetVersionInfo:
    """get_version_info collects runtime metadata."""

    def test_returns_version_info(self) -> None:
        info = get_version_info()
        assert isinstance(info, VersionInfo)

    def test_python_version_set(self) -> None:
        info = get_version_info()
        assert info.python_version
        assert "." in info.python_version  # e.g. "3.13.x ..."

    def test_build_time_set(self) -> None:
        info = get_version_info()
        assert info.build_time
        assert "T" in info.build_time  # ISO-8601-ish

    def test_no_git_repo_graceful(self) -> None:
        """When git commands fail, fields should be empty — no exception."""
        with patch("pykit_version.version.subprocess.run", side_effect=FileNotFoundError):
            info = get_version_info()
        assert info.git_commit == ""
        assert info.git_branch == ""
        assert not info.is_dirty

    def test_git_timeout_graceful(self) -> None:
        with patch(
            "pykit_version.version.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="git", timeout=5),
        ):
            info = get_version_info()
        assert info.git_commit == ""
        assert info.git_branch == ""

    def test_package_not_found_fallback(self) -> None:
        info = get_version_info("nonexistent-package-xyz")
        assert info.version == "dev"
        assert not info.is_release


class TestGetShortVersion:
    """get_short_version formats a concise version string."""

    def test_returns_string(self) -> None:
        result = get_short_version()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_with_commit(self) -> None:
        info = VersionInfo(
            version="1.0.0",
            git_commit="abc1234",
            git_branch="main",
            build_time="",
            python_version="3.13",
            is_release=True,
            is_dirty=False,
        )
        with patch("pykit_version.version.get_version_info", return_value=info):
            assert get_short_version() == "1.0.0-abc1234"

    def test_format_dirty(self) -> None:
        info = VersionInfo(
            version="1.0.0",
            git_commit="abc1234",
            git_branch="main",
            build_time="",
            python_version="3.13",
            is_release=True,
            is_dirty=True,
        )
        with patch("pykit_version.version.get_version_info", return_value=info):
            assert get_short_version() == "1.0.0-abc1234-dirty"

    def test_format_no_commit(self) -> None:
        info = VersionInfo(
            version="dev",
            git_commit="",
            git_branch="",
            build_time="",
            python_version="3.13",
            is_release=False,
            is_dirty=False,
        )
        with patch("pykit_version.version.get_version_info", return_value=info):
            assert get_short_version() == "dev"


class TestGetFullVersion:
    """get_full_version returns a detailed version string."""

    def test_returns_string(self) -> None:
        result = get_full_version()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_version_info(self) -> None:
        info = VersionInfo(
            version="1.0.0",
            git_commit="abc1234",
            git_branch="main",
            build_time="2024-01-01T00:00:00Z",
            python_version="3.13",
            is_release=True,
            is_dirty=False,
        )
        with patch("pykit_version.version.get_version_info", return_value=info):
            fv = get_full_version()
        assert "1.0.0" in fv
        assert "abc1234" in fv
        assert "built" in fv
        # main/master branches are excluded from full version
        assert "main" not in fv

    def test_feature_branch_included(self) -> None:
        info = VersionInfo(
            version="1.0.0",
            git_commit="abc1234",
            git_branch="feature/foo",
            build_time="2024-01-01T00:00:00Z",
            python_version="3.13",
            is_release=True,
            is_dirty=False,
        )
        with patch("pykit_version.version.get_version_info", return_value=info):
            fv = get_full_version()
        assert "feature/foo" in fv

    def test_dirty_included(self) -> None:
        info = VersionInfo(
            version="1.0.0",
            git_commit="abc1234",
            git_branch="main",
            build_time="2024-01-01T00:00:00Z",
            python_version="3.13",
            is_release=True,
            is_dirty=True,
        )
        with patch("pykit_version.version.get_version_info", return_value=info):
            fv = get_full_version()
        assert "dirty" in fv

    def test_dev_no_commit(self) -> None:
        info = VersionInfo(
            version="dev",
            git_commit="",
            git_branch="",
            build_time="2024-01-01T00:00:00Z",
            python_version="3.13",
            is_release=False,
            is_dirty=False,
        )
        with patch("pykit_version.version.get_version_info", return_value=info):
            fv = get_full_version()
        assert fv.startswith("dev")
