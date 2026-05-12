"""Tests for management-side protocols."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from pykit_git import BranchFilter, open_repo


def test_list_branches(tmp_repo: Path, create_branch: Callable[[Path, str], None]) -> None:
    create_branch(tmp_repo, "feature")
    repo = open_repo(tmp_repo)

    branches = repo.list_branches(BranchFilter.LOCAL)

    names = {branch.name for branch in branches}
    assert "feature" in names
    assert "main" in names or "master" in names


def test_list_tags(tmp_repo: Path, create_tag: Callable[[Path, str], None]) -> None:
    create_tag(tmp_repo, "v1.0.0")
    repo = open_repo(tmp_repo)

    tags = repo.list_tags()

    assert any(tag.name == "v1.0.0" for tag in tags)


def test_create_and_delete_branch(tmp_repo: Path) -> None:
    repo = open_repo(tmp_repo)

    repo.create_branch("feature", "HEAD")
    assert any(branch.name == "feature" for branch in repo.list_branches())

    repo.delete_branch("feature")
    assert all(branch.name != "feature" for branch in repo.list_branches())


def test_create_and_delete_tag(tmp_repo: Path) -> None:
    repo = open_repo(tmp_repo)

    repo.create_tag("v1.0.0", "HEAD", "release v1.0.0")
    tags = repo.list_tags()
    assert any(tag.name == "v1.0.0" and tag.message == "release v1.0.0" for tag in tags)

    repo.delete_tag("v1.0.0")
    assert all(tag.name != "v1.0.0" for tag in repo.list_tags())


def test_list_remotes(tmp_repo: Path) -> None:
    bare_remote = init_bare_remote(tmp_repo.parent / "origin.git")
    run_git(tmp_repo, "remote", "add", "origin", str(bare_remote))
    run_git(tmp_repo, "remote", "add", "backup", str(init_bare_remote(tmp_repo.parent / "backup.git")))
    repo = open_repo(tmp_repo)

    remotes = repo.list_remotes()

    assert [remote.name for remote in remotes] == ["backup", "origin"]
    assert remotes[1].url == str(bare_remote)
    assert remotes[1].fetch_specs == ("+refs/heads/*:refs/remotes/origin/*",)


def test_tracking_branch(tmp_repo: Path) -> None:
    bare_remote = init_bare_remote(tmp_repo.parent / "origin.git")
    run_git(tmp_repo, "remote", "add", "origin", str(bare_remote))
    run_git(tmp_repo, "push", "-u", "origin", "HEAD")
    repo = open_repo(tmp_repo)
    branch = run_git(tmp_repo, "branch", "--show-current").strip()

    assert repo.tracking_branch(branch) == f"origin/{branch}"


def test_config_get(tmp_repo: Path) -> None:
    repo = open_repo(tmp_repo)
    assert repo.config_get("user.name") == "Test User"


def test_config_get_all(tmp_repo: Path) -> None:
    run_git(tmp_repo, "config", "--add", "remote.origin.fetch", "+refs/heads/main:refs/remotes/origin/main")
    run_git(tmp_repo, "config", "--add", "remote.origin.fetch", "+refs/heads/dev:refs/remotes/origin/dev")
    repo = open_repo(tmp_repo)

    assert repo.config_get_all("remote.origin.fetch") == [
        "+refs/heads/main:refs/remotes/origin/main",
        "+refs/heads/dev:refs/remotes/origin/dev",
    ]


def test_config_set(tmp_repo: Path) -> None:
    repo = open_repo(tmp_repo)
    repo.config_set("demo.answer", "42")
    assert repo.config_get("demo.answer") == "42"


def init_bare_remote(path: Path) -> Path:
    subprocess.run(["git", "init", "--bare", str(path)], check=True, capture_output=True, text=True)
    return path.resolve()


def run_git(repo_dir: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo_dir, check=True, capture_output=True, text=True)
    return result.stdout
