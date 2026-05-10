"""Tests for repository orchestration."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from pykit_errors import AppError
from pykit_git import Repo, discover, init, init_bare, open


def test_open(tmp_repo: Path) -> None:
    repo = open(tmp_repo)
    assert isinstance(repo, Repo)
    assert repo.root == tmp_repo.resolve()


def test_init(tmp_path: Path) -> None:
    repo = init(tmp_path / "repo")

    assert isinstance(repo, Repo)
    assert repo.root == (tmp_path / "repo").resolve()
    assert (repo.root / ".git").is_dir()


def test_repo_init_classmethod(tmp_path: Path) -> None:
    repo = Repo.init(tmp_path / "repo")

    assert repo.root == (tmp_path / "repo").resolve()
    assert (repo.root / ".git").is_dir()


def test_init_bare(tmp_path: Path) -> None:
    repo = init_bare(tmp_path / "repo.git")

    assert isinstance(repo, Repo)
    assert repo.root == (tmp_path / "repo.git").resolve()
    assert (repo.root / "HEAD").is_file()
    assert not (repo.root / ".git").exists()


def test_repo_init_bare_classmethod(tmp_path: Path) -> None:
    repo = Repo.init_bare(tmp_path / "repo.git")

    assert repo.root == (tmp_path / "repo.git").resolve()
    assert (repo.root / "HEAD").is_file()
    assert not (repo.root / ".git").exists()


def test_open_nonexistent() -> None:
    with pytest.raises(AppError):
        open('/nonexistent/path')


def test_discover(tmp_repo: Path) -> None:
    subdir = tmp_repo / 'sub' / 'deep'
    subdir.mkdir(parents=True)
    repo = discover(subdir)
    assert repo.root == tmp_repo.resolve()


def test_head(tmp_repo: Path) -> None:
    repo = open(tmp_repo)
    ref = repo.head()
    assert not ref.target.is_zero()


def test_resolve_ref(tmp_repo: Path, create_branch: Callable[[Path, str], None]) -> None:
    create_branch(tmp_repo, 'feature')
    repo = open(tmp_repo)
    oid = repo.resolve_ref('feature')
    assert not oid.is_zero()


def test_rev_parse(tmp_repo: Path) -> None:
    repo = open(tmp_repo)
    assert repo.rev_parse('HEAD') == repo.resolve_ref('HEAD')


def test_resolve_ref_not_found(tmp_repo: Path) -> None:
    repo = open(tmp_repo)
    with pytest.raises(AppError):
        repo.resolve_ref('nonexistent')


def test_is_dirty_clean(tmp_repo: Path) -> None:
    repo = open(tmp_repo)
    assert not repo.is_dirty()


def test_is_dirty_modified(tmp_repo: Path, make_dirty: Callable[[Path, str], None]) -> None:
    make_dirty(tmp_repo, 'README.md')
    repo = open(tmp_repo)
    assert repo.is_dirty()


def test_is_dirty_untracked(tmp_repo: Path, make_untracked: Callable[[Path, str], None]) -> None:
    make_untracked(tmp_repo, 'new.txt')
    repo = open(tmp_repo)
    assert repo.is_dirty()
