"""CLI backend entrypoints."""

from __future__ import annotations

import subprocess
from pathlib import Path

from pykit_errors import AppError
from pykit_git.cli.exec_runner import SubprocessExecutor
from pykit_git.cli.manage import ManageBackend
from pykit_git.cli.read import ReadBackend
from pykit_git.cli.write import WriteBackend
from pykit_git.errors import detached_head, ref_not_found, repo_not_found, unborn_head
from pykit_git.types import Oid, Reference


class Backend(ReadBackend, WriteBackend, ManageBackend):
    """git CLI backend with read/write/manage support."""

    def __init__(self, root: Path, executor: SubprocessExecutor | None = None) -> None:
        self._root = root
        self._executor = executor or SubprocessExecutor(root)

    @property
    def root(self) -> Path:
        return self._root

    def exec(self, *args: str) -> bytes:
        return self._executor.exec(*args)

    def head(self) -> Reference:
        symbolic = self._executor.run("symbolic-ref", "HEAD")
        if symbolic.returncode != 0:
            stderr = symbolic.stderr.decode(errors="replace").strip().casefold()
            exc = subprocess.CalledProcessError(
                symbolic.returncode,
                ["git", "symbolic-ref", "HEAD"],
                output=symbolic.stdout,
                stderr=symbolic.stderr,
            )
            if "unborn" in stderr:
                raise unborn_head() from exc
            raise detached_head() from exc
        name = symbolic.stdout.decode(errors="replace").strip()
        try:
            target = self.rev_parse("HEAD")
        except AppError as exc:
            if exc.details.get("resource") == "ref":
                raise unborn_head() from exc
            raise
        return Reference(
            name=name,
            target=target,
            is_branch=name.startswith("refs/heads/"),
            is_tag=name.startswith("refs/tags/"),
        )

    def resolve_ref(self, refname: str) -> Oid:
        try:
            return self.rev_parse(refname)
        except ValueError as exc:
            raise ref_not_found(refname) from exc

    def is_dirty(self) -> bool:
        return bool(self._executor.exec("status", "--porcelain").strip())


def init(path: str | Path) -> Backend:
    """Initialize a new repository using git CLI."""
    abs_path = Path(path).resolve()
    abs_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(abs_path)], capture_output=True, check=True)
    return Backend(abs_path, executor=SubprocessExecutor(abs_path))


def init_bare(path: str | Path) -> Backend:
    """Initialize a new bare repository using git CLI."""
    abs_path = Path(path).resolve()
    abs_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--bare", str(abs_path)], capture_output=True, check=True)
    return Backend(abs_path, executor=SubprocessExecutor(abs_path))


def open(path: str | Path) -> Backend:
    """Open a repository using git CLI discovery."""
    abs_path = Path(path).resolve()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=abs_path,
            capture_output=True,
            check=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise repo_not_found(str(abs_path)) from exc
    root = Path(result.stdout.strip()).resolve()
    return Backend(root, executor=SubprocessExecutor(root))


def discover(path: str | Path) -> Backend:
    """Discover a repository using git CLI discovery."""
    return open(path)


def clone(url: str, path: str | Path) -> Backend:
    """Clone a repository using git CLI."""
    abs_path = Path(path).resolve()
    subprocess.run(["git", "clone", url, str(abs_path)], capture_output=True, check=True, text=True)
    return Backend(abs_path, executor=SubprocessExecutor(abs_path))
