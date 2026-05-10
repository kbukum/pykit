"""Tests for pykit-git."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Create a new git repo with an initial commit."""
    run_git(tmp_path, 'init')
    run_git(tmp_path, 'config', 'user.email', 'test@test.com')
    run_git(tmp_path, 'config', 'user.name', 'Test User')
    write_file(tmp_path, 'README.md', '# test repo')
    run_git(tmp_path, 'add', '.')
    run_git(tmp_path, 'commit', '-m', 'initial commit')
    return tmp_path


def write_file(repo_dir: Path, path: str, content: str) -> None:
    """Create or overwrite a file in the repo."""
    full = repo_dir / path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)


def run_git(repo_dir: Path, *args: str, env: dict[str, str] | None = None) -> str:
    """Run a git command in the test repository."""
    result = subprocess.run(
        ['git', *args],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    return result.stdout


def commit_file_impl(repo_dir: Path, path: str, content: str, message: str) -> None:
    """Add and commit a file."""
    write_file(repo_dir, path, content)
    run_git(repo_dir, 'add', path)
    run_git(repo_dir, 'commit', '-m', message)


def create_branch_impl(repo_dir: Path, name: str) -> None:
    """Create a new branch."""
    run_git(repo_dir, 'branch', name)


def create_tag_impl(repo_dir: Path, name: str) -> None:
    """Create a lightweight tag."""
    run_git(repo_dir, 'tag', name)


def make_dirty_impl(repo_dir: Path, path: str) -> None:
    """Modify a tracked file without committing."""
    write_file(repo_dir, path, 'dirty content\n')


def make_untracked_impl(repo_dir: Path, path: str) -> None:
    """Create an untracked file."""
    write_file(repo_dir, path, 'untracked\n')


@pytest.fixture
def commit_file() -> Callable[[Path, str, str, str], None]:
    return commit_file_impl


@pytest.fixture
def create_branch() -> Callable[[Path, str], None]:
    return create_branch_impl


@pytest.fixture
def create_tag() -> Callable[[Path, str], None]:
    return create_tag_impl


@pytest.fixture
def make_dirty() -> Callable[[Path, str], None]:
    return make_dirty_impl


@pytest.fixture
def make_untracked() -> Callable[[Path, str], None]:
    return make_untracked_impl
