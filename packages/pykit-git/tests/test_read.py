"""Tests for read-side protocols."""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from pykit_errors import AppError
from pykit_git import BlameOptions, EntryKind, EntryState, FileStatus, LogOptions, open


def test_diff_added(
    tmp_repo: Path,
    create_tag: Callable[[Path, str], None],
    commit_file: Callable[[Path, str, str, str], None],
) -> None:
    create_tag(tmp_repo, "v1")
    commit_file(tmp_repo, "new.txt", "hello", "add new file")
    repo = open(tmp_repo)

    entries = repo.diff("v1", "HEAD")
    assert entries
    assert any(entry.path == "new.txt" and entry.status == FileStatus.ADDED for entry in entries)


def test_diff_modified(
    tmp_repo: Path,
    create_tag: Callable[[Path, str], None],
    commit_file: Callable[[Path, str, str, str], None],
) -> None:
    create_tag(tmp_repo, "v1")
    commit_file(tmp_repo, "README.md", "updated", "update readme")
    repo = open(tmp_repo)

    entries = repo.diff("v1", "HEAD")
    assert any(entry.path == "README.md" and entry.status == FileStatus.MODIFIED for entry in entries)


def test_diff_stats(
    tmp_repo: Path,
    create_tag: Callable[[Path, str], None],
    commit_file: Callable[[Path, str, str, str], None],
) -> None:
    create_tag(tmp_repo, "v1")
    commit_file(tmp_repo, "a.txt", "line1\nline2\n", "add a")
    commit_file(tmp_repo, "b.txt", "line1\n", "add b")
    repo = open(tmp_repo)

    stats = repo.diff_stats("v1", "HEAD")
    assert stats.files_changed >= 2
    assert stats.additions >= 3


def test_status_clean(tmp_repo: Path) -> None:
    repo = open(tmp_repo)
    assert repo.status() == []


def test_status_dirty(
    tmp_repo: Path,
    make_untracked: Callable[[Path, str], None],
    make_dirty: Callable[[Path, str], None],
) -> None:
    make_untracked(tmp_repo, "untracked.txt")
    make_dirty(tmp_repo, "README.md")
    repo = open(tmp_repo)

    entries = repo.status()
    assert len(entries) >= 2
    assert any(entry.path == "untracked.txt" and entry.state == EntryState.UNTRACKED for entry in entries)


def test_file_at(tmp_repo: Path, commit_file: Callable[[Path, str, str, str], None]) -> None:
    commit_file(tmp_repo, "hello.txt", "hello world", "add hello")
    repo = open(tmp_repo)
    assert repo.file_at("HEAD", "hello.txt") == b"hello world"


def test_show_file(tmp_repo: Path, commit_file: Callable[[Path, str, str, str], None]) -> None:
    commit_file(tmp_repo, "hello.txt", "hello world", "add hello")
    repo = open(tmp_repo)
    assert repo.show("HEAD:hello.txt") == b"hello world"


def test_file_at_not_found(tmp_repo: Path) -> None:
    repo = open(tmp_repo)
    with pytest.raises(AppError):
        repo.file_at("HEAD", "nonexistent.txt")


def test_list_entries(tmp_repo: Path, commit_file: Callable[[Path, str, str, str], None]) -> None:
    commit_file(tmp_repo, "a.txt", "a", "add a")
    commit_file(tmp_repo, "sub/b.txt", "b", "add b")
    repo = open(tmp_repo)

    entries = repo.list_entries("HEAD", "")
    assert len(entries) >= 2
    assert any(entry.kind == EntryKind.BLOB for entry in entries)
    assert any(entry.kind == EntryKind.TREE for entry in entries)


def test_list_entries_subdir(tmp_repo: Path, commit_file: Callable[[Path, str, str, str], None]) -> None:
    commit_file(tmp_repo, "sub/file.txt", "content", "add sub/file")
    repo = open(tmp_repo)

    entries = repo.list_entries("HEAD", "sub")
    assert len(entries) == 1
    assert entries[0].name == "file.txt"


def test_tree_hash(tmp_repo: Path) -> None:
    repo = open(tmp_repo)
    assert not repo.tree_hash("HEAD", "").is_zero()


def test_tree_hash_changes(
    tmp_repo: Path,
    create_tag: Callable[[Path, str], None],
    commit_file: Callable[[Path, str, str, str], None],
) -> None:
    create_tag(tmp_repo, "v1")
    repo = open(tmp_repo)
    hash1 = repo.tree_hash("v1", "")

    commit_file(tmp_repo, "new.txt", "content", "add file")
    repo = open(tmp_repo)
    hash2 = repo.tree_hash("HEAD", "")

    assert hash1 != hash2


def test_log_with_options(tmp_repo: Path, commit_file: Callable[[Path, str, str, str], None]) -> None:
    commit_file(tmp_repo, "alpha.txt", "alpha\n", "add alpha")
    commit_file(tmp_repo, "notes/beta.txt", "beta\n", "add beta")
    repo = open(tmp_repo)

    commits = repo.log(LogOptions(max_count=1, path_filter="notes", author_filter="Test User"))

    assert len(commits) == 1
    assert commits[0].message == "add beta\n"


def test_log_since_and_until(tmp_repo: Path) -> None:
    older_when = datetime.fromisoformat("2024-01-01T00:00:00+00:00")
    newer_when = datetime.fromisoformat("2024-01-02T00:00:00+00:00")

    commit_with_date(tmp_repo, "alpha.txt", "alpha\n", "add alpha", older_when)
    repo = open(tmp_repo)
    older_commit = repo.log(LogOptions(max_count=1))[0]

    commit_with_date(tmp_repo, "beta.txt", "beta\n", "add beta", newer_when)
    repo = open(tmp_repo)
    newer_commit = repo.log(LogOptions(max_count=1))[0]

    since_commits = repo.log(
        LogOptions(since=older_commit.committer.when + timedelta(hours=12), path_filter="beta.txt")
    )
    until_commits = repo.log(LogOptions(until=older_commit.committer.when, path_filter="alpha.txt"))

    assert [commit.message for commit in since_commits] == [newer_commit.message]
    assert [commit.message for commit in until_commits] == [older_commit.message]


def test_merge_base(tmp_repo: Path, commit_file: Callable[[Path, str, str, str], None]) -> None:
    commit_file(tmp_repo, "shared.txt", "base\n", "base change")
    repo = open(tmp_repo)
    base = repo.resolve_ref("HEAD")

    repo.create_branch("feature", "HEAD")
    commit_file(tmp_repo, "main.txt", "main\n", "main change")
    repo = open(tmp_repo)
    main_head = repo.resolve_ref("HEAD")

    checkout(tmp_repo, "feature")
    commit_file(tmp_repo, "feature.txt", "feature\n", "feature change")
    repo = open(tmp_repo)

    assert repo.merge_base("HEAD", str(main_head)) == base


def test_is_ancestor(tmp_repo: Path, commit_file: Callable[[Path, str, str, str], None]) -> None:
    commit_file(tmp_repo, "base.txt", "base\n", "base change")
    repo = open(tmp_repo)
    ancestor = repo.resolve_ref("HEAD")

    commit_file(tmp_repo, "desc.txt", "desc\n", "desc change")
    repo = open(tmp_repo)
    descendant = repo.resolve_ref("HEAD")

    assert repo.is_ancestor(str(ancestor), str(descendant))
    assert not repo.is_ancestor(str(descendant), str(ancestor))


def test_blame(tmp_repo: Path, commit_file: Callable[[Path, str, str, str], None]) -> None:
    commit_file(tmp_repo, "story.txt", "line one\n", "add first line")
    commit_file(tmp_repo, "story.txt", "line one\nline two\n", "add second line")
    repo = open(tmp_repo)

    lines = repo.blame("HEAD", "story.txt")

    assert [line.line for line in lines] == [1, 2]
    assert [line.content for line in lines] == ["line one", "line two"]
    assert lines[0].commit_oid != lines[1].commit_oid


def test_blame_with_options(tmp_repo: Path, commit_file: Callable[[Path, str, str, str], None]) -> None:
    commit_file(tmp_repo, "story.txt", "line one\n", "add first line")
    commit_file(tmp_repo, "story.txt", "line one\nline two\n", "add second line")
    repo = open(tmp_repo)

    lines = repo.blame("HEAD", "story.txt", BlameOptions(start_line=2, end_line=2))

    assert len(lines) == 1
    assert lines[0].line == 2
    assert lines[0].content == "line two"


def test_describe_exact_tag(tmp_repo: Path, create_tag: Callable[[Path, str], None]) -> None:
    create_tag(tmp_repo, "v1")
    repo = open(tmp_repo)
    assert repo.describe() == "v1"


def test_grep(tmp_repo: Path, commit_file: Callable[[Path, str, str, str], None]) -> None:
    commit_file(tmp_repo, "notes.txt", "alpha\nbeta\n", "add notes")
    repo = open(tmp_repo)
    matches = repo.grep("beta", "HEAD")
    assert len(matches) == 1
    assert matches[0].path == "notes.txt"
    assert matches[0].line == 2
    assert matches[0].column == re.search("beta", matches[0].content).start() + 1


def checkout(repo_dir: Path, refname: str) -> None:
    subprocess.run(["git", "checkout", refname], cwd=repo_dir, check=True, capture_output=True, text=True)


def commit_with_date(repo_dir: Path, path: str, content: str, message: str, when: datetime) -> None:
    full_path = repo_dir / path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content)

    env = os.environ | {"GIT_AUTHOR_DATE": when.isoformat(), "GIT_COMMITTER_DATE": when.isoformat()}
    subprocess.run(["git", "add", path], cwd=repo_dir, check=True, capture_output=True, text=True, env=env)
    subprocess.run(
        ["git", "commit", "-m", message], cwd=repo_dir, check=True, capture_output=True, text=True, env=env
    )
