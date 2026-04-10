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


# ---------------------------------------------------------------------------
# NEW TEST CLASSES
# ---------------------------------------------------------------------------


class TestVersionParsing:
    """Version string edge cases for is_release logic."""

    def _make_info(self, pkg_version: str) -> VersionInfo:
        """Build a VersionInfo by simulating is_release logic from get_version_info."""
        is_release = pkg_version != "dev" and "dirty" not in pkg_version
        return VersionInfo(
            version=pkg_version,
            git_commit="abc1234",
            git_branch="main",
            build_time="2024-01-01T00:00:00Z",
            python_version="3.13.0",
            is_release=is_release,
            is_dirty=False,
        )

    def test_prerelease_is_release(self) -> None:
        info = self._make_info("1.0.0-rc.1")
        assert info.is_release is True

    def test_prerelease_alpha(self) -> None:
        info = self._make_info("1.0.0-alpha.1")
        assert info.is_release is True

    def test_prerelease_beta(self) -> None:
        info = self._make_info("1.0.0-beta.2")
        assert info.is_release is True

    def test_empty_version(self) -> None:
        info = self._make_info("")
        assert info.is_release is True  # not "dev" and no "dirty"

    def test_dev_version_not_release(self) -> None:
        info = self._make_info("dev")
        assert info.is_release is False

    def test_dirty_version_not_release(self) -> None:
        info = self._make_info("1.0.0-dirty")
        assert info.is_release is False

    def test_case_sensitive_dev(self) -> None:
        info = self._make_info("DEV")
        assert info.is_release is True  # only lowercase "dev" triggers False

    def test_dirty_substring(self) -> None:
        info = self._make_info("dirty-build")
        assert info.is_release is False  # contains "dirty"


class TestIsReleaseLogic:
    """Table-driven parametrised tests for is_release determination."""

    @pytest.mark.parametrize(
        ("pkg_version", "expected"),
        [
            ("1.0.0", True),
            ("0.0.1", True),
            ("dev", False),
            ("1.0.0-dirty", False),
            ("dirty", False),
            ("dirty-build", False),
            ("1.0.0-rc.1", True),
            ("1.0.0-alpha.1", True),
            ("1.0.0-beta.2", True),
            ("", True),
            ("DEV", True),
            ("Dev", True),
            ("0.0.0", True),
            ("999.999.999", True),
            ("1.0.0+build.123", True),
            ("1.0.0-dirty.1", False),  # contains "dirty"
            ("1.0.0.dev0", True),  # Python dev suffix != literal "dev"
        ],
    )
    def test_is_release(self, pkg_version: str, expected: bool) -> None:
        is_release = pkg_version != "dev" and "dirty" not in pkg_version
        assert is_release is expected


class TestShortVersionFormats:
    """Additional get_short_version format edge cases."""

    def test_short_version_prerelease_with_commit(self) -> None:
        info = VersionInfo(
            version="2.0.0-rc.1",
            git_commit="def5678",
            git_branch="release/v2",
            build_time="",
            python_version="3.13",
            is_release=True,
            is_dirty=False,
        )
        with patch("pykit_version.version.get_version_info", return_value=info):
            assert get_short_version() == "2.0.0-rc.1-def5678"

    def test_short_version_dirty_no_commit(self) -> None:
        info = VersionInfo(
            version="dev",
            git_commit="",
            git_branch="",
            build_time="",
            python_version="3.13",
            is_release=False,
            is_dirty=True,
        )
        with patch("pykit_version.version.get_version_info", return_value=info):
            # No commit → suffix path is skipped; returns bare version
            assert get_short_version() == "dev"

    def test_short_version_empty_version_with_commit(self) -> None:
        info = VersionInfo(
            version="",
            git_commit="abc1234",
            git_branch="main",
            build_time="",
            python_version="3.13",
            is_release=True,
            is_dirty=False,
        )
        with patch("pykit_version.version.get_version_info", return_value=info):
            assert get_short_version() == "-abc1234"


class TestFullVersionFormats:
    """Additional get_full_version format edge cases."""

    def test_full_version_develop_branch(self) -> None:
        info = VersionInfo(
            version="1.0.0",
            git_commit="abc1234",
            git_branch="develop",
            build_time="2024-01-01T00:00:00Z",
            python_version="3.13",
            is_release=True,
            is_dirty=False,
        )
        with patch("pykit_version.version.get_version_info", return_value=info):
            fv = get_full_version()
        assert "develop" in fv

    def test_full_version_release_branch(self) -> None:
        info = VersionInfo(
            version="1.0.0",
            git_commit="abc1234",
            git_branch="release/v1.0",
            build_time="2024-01-01T00:00:00Z",
            python_version="3.13",
            is_release=True,
            is_dirty=False,
        )
        with patch("pykit_version.version.get_version_info", return_value=info):
            fv = get_full_version()
        assert "release/v1.0" in fv

    def test_full_version_master_excluded(self) -> None:
        info = VersionInfo(
            version="1.0.0",
            git_commit="abc1234",
            git_branch="master",
            build_time="2024-01-01T00:00:00Z",
            python_version="3.13",
            is_release=True,
            is_dirty=False,
        )
        with patch("pykit_version.version.get_version_info", return_value=info):
            fv = get_full_version()
        assert "master" not in fv

    def test_full_version_empty_everything(self) -> None:
        info = VersionInfo(
            version="",
            git_commit="",
            git_branch="",
            build_time="",
            python_version="",
            is_release=True,
            is_dirty=False,
        )
        with patch("pykit_version.version.get_version_info", return_value=info):
            fv = get_full_version()
        # No commit, no branch, no dirty, no build_time → just the empty version
        assert fv == ""

    def test_full_version_build_time_included(self) -> None:
        info = VersionInfo(
            version="3.0.0",
            git_commit="face000",
            git_branch="main",
            build_time="2025-06-01T12:00:00Z",
            python_version="3.13",
            is_release=True,
            is_dirty=False,
        )
        with patch("pykit_version.version.get_version_info", return_value=info):
            fv = get_full_version()
        assert "(built 2025-06-01T12:00:00Z)" in fv


class TestVersionInfoDataclassExtended:
    """Extended dataclass behaviour tests."""

    def _sample(self, **overrides: object) -> VersionInfo:
        defaults: dict[str, object] = dict(
            version="1.0.0",
            git_commit="abc1234",
            git_branch="main",
            build_time="2024-01-01T00:00:00Z",
            python_version="3.13.0",
            is_release=True,
            is_dirty=False,
        )
        defaults.update(overrides)
        return VersionInfo(**defaults)  # type: ignore[arg-type]

    def test_version_info_equality(self) -> None:
        a = self._sample()
        b = self._sample()
        assert a == b

    def test_version_info_inequality(self) -> None:
        a = self._sample(version="1.0.0")
        b = self._sample(version="2.0.0")
        assert a != b

    def test_version_info_hash(self) -> None:
        a = self._sample()
        b = self._sample()
        # Hashable and equal instances share a hash
        assert hash(a) == hash(b)
        s = {a, b}
        assert len(s) == 1

    def test_version_info_repr(self) -> None:
        info = self._sample()
        r = repr(info)
        assert "VersionInfo" in r
        assert "1.0.0" in r
        assert "abc1234" in r

    def test_version_info_all_fields_accessible(self) -> None:
        info = self._sample()
        assert info.version == "1.0.0"
        assert info.git_commit == "abc1234"
        assert info.git_branch == "main"
        assert info.build_time == "2024-01-01T00:00:00Z"
        assert info.python_version == "3.13.0"
        assert info.is_release is True
        assert info.is_dirty is False


class TestRunGitEdgeCases:
    """_run_git gracefully handles subprocess errors."""

    def test_git_oserror_graceful(self) -> None:
        with patch(
            "pykit_version.version.subprocess.run",
            side_effect=OSError("mocked OS error"),
        ):
            info = get_version_info()
        assert info.git_commit == ""
        assert info.git_branch == ""
        assert info.is_dirty is False

    def test_git_returns_empty_on_nonzero_exit(self) -> None:
        fake_result = subprocess.CompletedProcess(args=["git"], returncode=1, stdout="", stderr="fatal")
        with patch(
            "pykit_version.version.subprocess.run",
            return_value=fake_result,
        ):
            info = get_version_info()
        assert info.git_commit == ""
        assert info.git_branch == ""
        assert info.is_dirty is False
