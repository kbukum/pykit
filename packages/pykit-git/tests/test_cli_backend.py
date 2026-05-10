"""Tests for the git CLI backend."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from pykit_errors import AppError
from pykit_git import CleanOptions, DescribeOptions, ResetMode
from pykit_git.auth.transport import SSHKey
from pykit_git.cli import init as cli_init
from pykit_git.cli import init_bare as cli_init_bare
from pykit_git.cli import open as cli_open
from pykit_git.cli.auth import build_env


def test_cli_init(tmp_path: Path) -> None:
    repo = cli_init(tmp_path / "repo")

    assert repo.root == (tmp_path / "repo").resolve()
    assert (repo.root / ".git").is_dir()


def test_cli_init_bare(tmp_path: Path) -> None:
    repo = cli_init_bare(tmp_path / "repo.git")

    assert repo.root == (tmp_path / "repo.git").resolve()
    assert (repo.root / "HEAD").is_file()
    assert not (repo.root / ".git").exists()


def test_cli_build_env_uses_private_key_for_identity() -> None:
    env = build_env(
        SSHKey(username="git", private_key_path="/keys/id_ed25519", public_key_path="/keys/id_ed25519.pub")
    )

    assert env["GIT_SSH_COMMAND"] == ("ssh -i /keys/id_ed25519 -o CertificateFile=/keys/id_ed25519.pub")


def test_cli_head_unborn_branch_raises_invalid_input(tmp_path: Path) -> None:
    repo = cli_init(tmp_path / "repo")

    with pytest.raises(AppError) as exc_info:
        repo.head()

    assert exc_info.value.details["field"] == "HEAD"
    assert "unborn HEAD" in exc_info.value.message


def test_cli_rev_parse_and_describe(tmp_repo: Path, create_tag: Callable[[Path, str], None]) -> None:
    create_tag(tmp_repo, "v1")
    repo = cli_open(tmp_repo)

    assert repo.describe() == "v1"
    assert repo.rev_parse("HEAD") == repo.resolve_ref("HEAD")
    assert repo.describe(DescribeOptions(abbreviated=True)) == "v1"


def test_cli_stage_and_commit(tmp_repo: Path, make_dirty: Callable[[Path, str], None]) -> None:
    make_dirty(tmp_repo, "README.md")
    repo = cli_open(tmp_repo)

    repo.stage("README.md")
    staged = repo.staged_entries()
    oid = repo.commit("update readme from cli")

    assert [entry.path for entry in staged] == ["README.md"]
    assert str(oid) == str(repo.rev_parse("HEAD"))


def test_cli_merge_reset_and_checkout(
    tmp_repo: Path, commit_file: Callable[[Path, str, str, str], None]
) -> None:
    repo = cli_open(tmp_repo)
    base = repo.rev_parse("HEAD")
    repo.create_branch("feature", "HEAD")

    repo.checkout("feature")
    commit_file(tmp_repo, "feature.txt", "feature\n", "feature change")
    feature_head = cli_open(tmp_repo).rev_parse("HEAD")

    repo = cli_open(tmp_repo)
    default_branch = "main" if any(branch.name == "main" for branch in repo.list_branches()) else "master"
    repo.checkout(default_branch)
    merge_result = repo.merge("feature")

    assert merge_result.merged
    assert repo.is_dirty() is False
    assert (tmp_repo / "feature.txt").exists()

    repo.reset(str(base), ResetMode.HARD)
    assert repo.rev_parse("HEAD") == base
    assert not (tmp_repo / "feature.txt").exists()

    repo.checkout("feature")
    assert repo.rev_parse("HEAD") == feature_head


def test_cli_stash_push_list_and_pop(tmp_repo: Path, make_dirty: Callable[[Path, str], None]) -> None:
    make_dirty(tmp_repo, "README.md")
    repo = cli_open(tmp_repo)

    stash_oid = repo.stash("save work")
    stashes = repo.stash_list()

    assert str(stash_oid) == str(stashes[0].oid)
    assert stashes[0].message == "On master: save work" or stashes[0].message == "On main: save work"
    assert not repo.is_dirty()

    repo.stash_pop()
    assert repo.is_dirty()
    assert repo.stash_list() == []


def test_cli_gc_and_clean(tmp_repo: Path, make_untracked: Callable[[Path, str], None]) -> None:
    make_untracked(tmp_repo, "junk.txt")
    repo = cli_open(tmp_repo)

    cleaned = repo.clean(CleanOptions())
    repo.gc()
    repo.prune()

    assert cleaned == ["junk.txt"]
    assert not (tmp_repo / "junk.txt").exists()
