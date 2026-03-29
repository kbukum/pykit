"""Build metadata and version info mirroring gokit version/."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version


@dataclass(frozen=True)
class VersionInfo:
    """Immutable snapshot of build/version metadata."""

    version: str
    git_commit: str
    git_branch: str
    build_time: str
    python_version: str
    is_release: bool
    is_dirty: bool


def _run_git(*args: str) -> str:
    """Run a git command and return stripped stdout, or empty string on failure."""
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return ""


def get_version_info(package_name: str = "pykit") -> VersionInfo:
    """Collect version metadata from package info, git, and the runtime."""
    # Package version via importlib.metadata
    try:
        pkg_version = version(package_name)
    except PackageNotFoundError:
        pkg_version = "dev"

    # Git metadata (safe - returns "" on any failure)
    git_commit = _run_git("rev-parse", "--short", "HEAD")
    git_branch = _run_git("rev-parse", "--abbrev-ref", "HEAD")
    dirty_output = _run_git("status", "--porcelain")
    is_dirty = bool(dirty_output)

    # Build time: current UTC timestamp
    build_time = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    is_release = pkg_version != "dev" and "dirty" not in pkg_version

    return VersionInfo(
        version=pkg_version,
        git_commit=git_commit,
        git_branch=git_branch,
        build_time=build_time,
        python_version=sys.version,
        is_release=is_release,
        is_dirty=is_dirty,
    )


def get_short_version(package_name: str = "pykit") -> str:
    """Return ``version-commit`` or just ``version`` when commit is unknown."""
    info = get_version_info(package_name)
    if info.git_commit:
        suffix = f"-{info.git_commit}"
        if info.is_dirty:
            suffix += "-dirty"
        return f"{info.version}{suffix}"
    return info.version


def get_full_version(package_name: str = "pykit") -> str:
    """Return a detailed version string including branch and build time."""
    info = get_version_info(package_name)
    parts: list[str] = [info.version]

    if info.git_commit:
        parts.append(info.git_commit)

    if info.git_branch and info.git_branch not in ("main", "master"):
        parts.append(info.git_branch)

    if info.is_dirty:
        parts.append("dirty")

    version_str = "-".join(parts)

    if info.build_time:
        version_str += f" (built {info.build_time})"

    return version_str
