"""Tests for write-side protocols."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pykit_git import CommitOptions, EntryState, Signature, open


def test_stage_files(tmp_repo: Path, make_dirty: Callable[[Path, str], None]) -> None:
    make_dirty(tmp_repo, "README.md")
    repo = open(tmp_repo)

    repo.stage("README.md")

    entries = repo.staged_entries()
    assert len(entries) == 1
    assert any(entry.path == "README.md" and entry.state == EntryState.STAGED for entry in entries)


def test_unstage(tmp_repo: Path, make_dirty: Callable[[Path, str], None]) -> None:
    make_dirty(tmp_repo, "README.md")
    repo = open(tmp_repo)
    repo.stage("README.md")

    repo.unstage("README.md")

    assert repo.staged_entries() == []


def test_staged_entries(tmp_repo: Path, make_dirty: Callable[[Path, str], None]) -> None:
    make_dirty(tmp_repo, "README.md")
    repo = open(tmp_repo)
    repo.stage("README.md")

    entries = repo.staged_entries()

    assert len(entries) == 1
    assert entries[0].path == "README.md"
    assert entries[0].state == EntryState.STAGED


def test_commit_with_message(tmp_repo: Path, make_dirty: Callable[[Path, str], None]) -> None:
    make_dirty(tmp_repo, "README.md")
    repo = open(tmp_repo)
    repo.stage("README.md")

    oid = repo.commit("update readme")
    commits = repo.log()

    assert str(oid) == str(commits[0].oid)
    assert commits[0].message == "update readme"


def test_commit_with_options(tmp_repo: Path, make_dirty: Callable[[Path, str], None]) -> None:
    make_dirty(tmp_repo, "README.md")
    repo = open(tmp_repo)
    repo.stage("README.md")

    when = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
    author = Signature(name="Author User", email="author@example.com", when=when)
    committer = Signature(name="Committer User", email="committer@example.com", when=when)

    oid = repo.commit("update readme", CommitOptions(author=author, committer=committer))
    commit = repo.log()[0]

    assert str(oid) == str(commit.oid)
    assert commit.author.name == "Author User"
    assert commit.author.email == "author@example.com"
    assert commit.committer.name == "Committer User"
    assert commit.committer.email == "committer@example.com"
