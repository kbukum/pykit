"""Repository orchestrator."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pykit_git.core.executor import Executor
from pykit_git.core.repository import Repository
from pykit_git.embedded import repo as embedded_repo
from pykit_git.manage.config import ConfigReader
from pykit_git.manage.maintain import Maintainer
from pykit_git.manage.refs import RefManager
from pykit_git.manage.remote import RemoteManager
from pykit_git.options import (
    BlameOptions,
    CheckoutOptions,
    CherryPickOptions,
    CleanOptions,
    CommitOptions,
    DescribeOptions,
    FetchOptions,
    GrepOptions,
    LogOptions,
    MergeOptions,
    PushOptions,
    RebaseOptions,
)
from pykit_git.read.blame import Blamer
from pykit_git.read.differ import Differ
from pykit_git.read.inspector import Inspector
from pykit_git.read.log import LogReader
from pykit_git.read.tree import TreeReader
from pykit_git.types import (
    BlameLine,
    Branch,
    BranchFilter,
    Commit,
    DiffEntry,
    DiffStats,
    GrepMatch,
    MergeResult,
    Oid,
    RebaseResult,
    Reference,
    Remote,
    ResetMode,
    StashEntry,
    StatusEntry,
    Tag,
    TreeEntry,
    TreeHash,
)
from pykit_git.write.checkout import Checker
from pykit_git.write.cherrypick import CherryPicker
from pykit_git.write.commit import Committer
from pykit_git.write.index import IndexManager
from pykit_git.write.merge import Merger
from pykit_git.write.rebase import Rebaser
from pykit_git.write.reset import Resetter
from pykit_git.write.stash import Stasher


class RepoBackend(
    Repository,
    Executor,
    Differ,
    TreeReader,
    LogReader,
    Blamer,
    Inspector,
    IndexManager,
    Committer,
    Merger,
    Rebaser,
    CherryPicker,
    Resetter,
    Checker,
    Stasher,
    RefManager,
    RemoteManager,
    ConfigReader,
    Maintainer,
    Protocol,
):
    """Composite protocol for git repository backends."""


class Repo:
    """High-level repository facade that delegates to a backend."""

    def __init__(self, backend: RepoBackend) -> None:
        self._backend = backend

    @classmethod
    def open(cls, path: str | Path) -> Repo:
        """Open a repository using the default backend."""
        return cls(embedded_repo.open(path))

    @classmethod
    def discover(cls, path: str | Path) -> Repo:
        """Discover a repository using the default backend."""
        return cls(embedded_repo.discover(path))

    @classmethod
    def clone(cls, url: str, path: str | Path) -> Repo:
        """Clone a repository using the default backend."""
        return cls(embedded_repo.clone(url, path))

    @classmethod
    def init(cls, path: str | Path) -> Repo:
        """Initialize a new repository."""
        return cls(embedded_repo.init(path))

    @classmethod
    def init_bare(cls, path: str | Path) -> Repo:
        """Initialize a new bare repository."""
        return cls(embedded_repo.init_bare(path))

    @property
    def root(self) -> Path:
        return self._backend.root

    def head(self) -> Reference:
        return self._backend.head()

    def resolve_ref(self, refname: str) -> Oid:
        return self._backend.resolve_ref(refname)

    def is_dirty(self) -> bool:
        return self._backend.is_dirty()

    def exec(self, *args: str) -> bytes:
        return self._backend.exec(*args)

    def diff(self, from_ref: str, to_ref: str) -> list[DiffEntry]:
        return self._backend.diff(from_ref, to_ref)

    def diff_stats(self, from_ref: str, to_ref: str) -> DiffStats:
        return self._backend.diff_stats(from_ref, to_ref)

    def status(self) -> list[StatusEntry]:
        return self._backend.status()

    def tree_hash(self, revision: str, path: str) -> TreeHash:
        return self._backend.tree_hash(revision, path)

    def file_at(self, revision: str, path: str) -> bytes:
        return self._backend.file_at(revision, path)

    def list_entries(self, revision: str, path: str) -> list[TreeEntry]:
        return self._backend.list_entries(revision, path)

    def log(self, opts: LogOptions | None = None) -> list[Commit]:
        return self._backend.log(opts)

    def merge_base(self, a: str, b: str) -> Oid:
        return self._backend.merge_base(a, b)

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        return self._backend.is_ancestor(ancestor, descendant)

    def blame(self, revision: str, path: str, opts: BlameOptions | None = None) -> list[BlameLine]:
        return self._backend.blame(revision, path, opts)

    def describe(self, opts: DescribeOptions | None = None) -> str:
        return self._backend.describe(opts)

    def rev_parse(self, revision: str) -> Oid:
        return self._backend.rev_parse(revision)

    def grep(self, pattern: str, revision: str, opts: GrepOptions | None = None) -> list[GrepMatch]:
        return self._backend.grep(pattern, revision, opts)

    def show(self, object_spec: str) -> bytes:
        return self._backend.show(object_spec)

    def stage(self, *paths: str) -> None:
        self._backend.stage(*paths)

    def unstage(self, *paths: str) -> None:
        self._backend.unstage(*paths)

    def staged_entries(self) -> list[StatusEntry]:
        return self._backend.staged_entries()

    def commit(self, message: str, opts: CommitOptions | None = None) -> Oid:
        return self._backend.commit(message, opts)

    def merge(self, branch: str, opts: MergeOptions | None = None) -> MergeResult:
        return self._backend.merge(branch, opts)

    def abort_merge(self) -> None:
        self._backend.abort_merge()

    def merge_abort(self) -> None:
        self._backend.merge_abort()

    def rebase(self, onto: str, opts: RebaseOptions | None = None) -> RebaseResult:
        return self._backend.rebase(onto, opts)

    def abort_rebase(self) -> None:
        self._backend.abort_rebase()

    def rebase_abort(self) -> None:
        self._backend.rebase_abort()

    def continue_rebase(self) -> RebaseResult:
        return self._backend.continue_rebase()

    def rebase_continue(self) -> RebaseResult:
        return self._backend.rebase_continue()

    def cherry_pick(self, commit: str, opts: CherryPickOptions | None = None) -> Oid:
        return self._backend.cherry_pick(commit, opts)

    def cherry_pick_continue(self) -> Oid:
        return self._backend.cherry_pick_continue()

    def cherry_pick_abort(self) -> None:
        self._backend.cherry_pick_abort()

    def reset(self, target: str, mode: ResetMode) -> None:
        self._backend.reset(target, mode)

    def checkout(self, ref_name: str, opts: CheckoutOptions | None = None) -> None:
        self._backend.checkout(ref_name, opts)

    def checkout_files(self, *paths: str) -> None:
        self._backend.checkout_files(*paths)

    def stash(self, message: str) -> Oid:
        return self._backend.stash(message)

    def stash_push(self, message: str) -> Oid:
        return self._backend.stash_push(message)

    def stash_pop(self, index: int = 0) -> None:
        self._backend.stash_pop(index)

    def stash_list(self) -> list[StashEntry]:
        return self._backend.stash_list()

    def list_branches(self, filter: BranchFilter = BranchFilter.LOCAL) -> list[Branch]:
        return self._backend.list_branches(filter)

    def list_tags(self) -> list[Tag]:
        return self._backend.list_tags()

    def create_branch(self, name: str, target: str) -> None:
        self._backend.create_branch(name, target)

    def delete_branch(self, name: str) -> None:
        self._backend.delete_branch(name)

    def create_tag(self, name: str, target: str, message: str) -> None:
        self._backend.create_tag(name, target, message)

    def delete_tag(self, name: str) -> None:
        self._backend.delete_tag(name)

    def list_remotes(self) -> list[Remote]:
        return self._backend.list_remotes()

    def fetch(self, remote: str, opts: FetchOptions | None = None) -> None:
        self._backend.fetch(remote, opts)

    def push(self, remote: str, opts: PushOptions | None = None) -> None:
        self._backend.push(remote, opts)

    def tracking_branch(self, branch: str) -> str:
        return self._backend.tracking_branch(branch)

    def config_get(self, key: str) -> str:
        return self._backend.config_get(key)

    def config_get_all(self, key: str) -> list[str]:
        return self._backend.config_get_all(key)

    def config_set(self, key: str, value: str) -> None:
        self._backend.config_set(key, value)

    def gc(self) -> None:
        self._backend.gc()

    def prune(self) -> None:
        self._backend.prune()

    def fsck(self) -> None:
        self._backend.fsck()

    def clean(self, opts: CleanOptions | None = None) -> list[str]:
        return self._backend.clean(opts)


def open(path: str | Path) -> Repo:
    """Open a repository using the default backend."""
    return Repo.open(path)


def discover(path: str | Path) -> Repo:
    """Discover a repository using the default backend."""
    return Repo.discover(path)


def clone(url: str, path: str | Path) -> Repo:
    """Clone a repository using the default backend."""
    return Repo.clone(url, path)


def init(path: str | Path) -> Repo:
    """Initialize a new repository."""
    return Repo.init(path)


def init_bare(path: str | Path) -> Repo:
    """Initialize a new bare repository."""
    return Repo.init_bare(path)
