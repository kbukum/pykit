"""Fluent builder for test git repositories."""

from __future__ import annotations

import shutil
import subprocess
import uuid
from pathlib import Path

from pykit_git import repo as git_repo


class RepoBuilder:
    """Creates test repositories with specific states.

    Uses temporary directories that are automatically cleaned up.

    Example::

        builder = RepoBuilder()
        builder.with_file("README.md", "hello")
        builder.with_commit("initial commit")
        builder.with_branch("feature")

        repo = builder.repo
        # Use repo for testing...

        builder.cleanup()  # Or use as context manager
    """

    def __init__(self, path: Path | None = None) -> None:
        if path is None:
            self._tmpdir = (Path.cwd() / ".pykit-git-testutil" / uuid.uuid4().hex).resolve()
            self._root = self._tmpdir
        else:
            self._tmpdir = None
            self._root = Path(path).resolve()
        self._repo = git_repo.init(self._root)
        self._repo.config_set("user.name", "Test User")
        self._repo.config_set("user.email", "test@example.com")

    def with_file(self, path: str, content: str) -> RepoBuilder:
        """Create or overwrite a file in the working tree."""
        full_path = self._root / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        return self

    def with_commit(self, message: str) -> RepoBuilder:
        """Stage all changes and create a commit."""
        self._repo.stage()
        self._repo.commit(message)
        return self

    def with_branch(self, name: str) -> RepoBuilder:
        """Create a new branch at HEAD."""
        self._repo.create_branch(name, "HEAD")
        return self

    def with_checkout(self, branch: str) -> RepoBuilder:
        """Switch to the named branch."""
        subprocess.run(
            ["git", "checkout", branch], cwd=self._root, capture_output=True, check=True, text=True
        )
        return self

    def with_tag(self, name: str, message: str = "") -> RepoBuilder:
        """Create a tag at HEAD."""
        self._repo.create_tag(name, "HEAD", message)
        return self

    @property
    def repo(self) -> git_repo.Repo:
        return self._repo

    @property
    def root(self) -> Path:
        return self._root

    def cleanup(self) -> None:
        """Remove the temporary directory if one was created."""
        if self._tmpdir is None:
            return
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        parent = self._tmpdir.parent
        try:
            parent.rmdir()
        except OSError:
            pass

    def __enter__(self) -> RepoBuilder:
        return self

    def __exit__(self, *args: object) -> None:
        self.cleanup()
