"""Tests for test utilities."""

from __future__ import annotations

from pathlib import Path

from pykit_git.testutil import RepoBuilder


def test_repo_builder_creates_repo_with_files_and_commits() -> None:
    builder = RepoBuilder()
    try:
        builder.with_file("README.md", "hello\n").with_commit("initial commit")

        assert builder.repo.root == builder.root
        assert builder.repo.file_at("HEAD", "README.md") == b"hello\n"
        assert not builder.repo.rev_parse("HEAD").is_zero()
    finally:
        builder.cleanup()


def test_repo_builder_creates_branches_and_tags() -> None:
    builder = RepoBuilder()
    try:
        builder.with_file("README.md", "hello\n").with_commit("initial commit")
        builder.with_branch("feature").with_tag("v1.0.0", "release")

        assert any(branch.name == "feature" for branch in builder.repo.list_branches())
        assert any(tag.name == "v1.0.0" and tag.message == "release" for tag in builder.repo.list_tags())
    finally:
        builder.cleanup()


def test_repo_builder_checkout_works() -> None:
    builder = RepoBuilder()
    try:
        builder.with_file("README.md", "hello\n").with_commit("initial commit")
        builder.with_branch("feature").with_checkout("feature")

        assert builder.repo.head().name == "refs/heads/feature"
    finally:
        builder.cleanup()


def test_repo_builder_context_manager_cleanup_works() -> None:
    root: Path | None = None

    with RepoBuilder() as builder:
        root = builder.root
        builder.with_file("README.md", "hello\n").with_commit("initial commit")
        assert root.exists()

    assert root is not None
    assert not root.exists()


def test_repo_builder_repo_can_be_used_for_assertions() -> None:
    builder = RepoBuilder()
    try:
        builder.with_file("README.md", "hello\n").with_commit("initial commit")

        repo = builder.repo

        assert repo.config_get("user.name") == "Test User"
        assert repo.is_dirty() is False
    finally:
        builder.cleanup()
