"""pygit2 backend entrypoints."""

from __future__ import annotations

from pathlib import Path

import pygit2

from pykit_git.embedded import manage, read, write
from pykit_git.errors import (
    detached_head,
    network_error,
    operation_not_supported,
    ref_not_found,
    repo_not_found,
)
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


class Backend:
    """Git repository backed by pygit2 (libgit2)."""

    def __init__(self, repo: pygit2.Repository, root: Path) -> None:
        self._repo = repo
        self._root = root

    @property
    def root(self) -> Path:
        """Absolute path to the repository root."""
        return self._root

    def head(self) -> Reference:
        """Return the reference that HEAD points to."""
        try:
            head = self._repo.head
        except pygit2.GitError as exc:
            raise detached_head() from exc
        return reference_from_pygit2(head)

    def resolve_ref(self, refname: str) -> Oid:
        """Resolve a ref name to an OID."""
        return read.rev_parse(self._repo, refname)

    def is_dirty(self) -> bool:
        """Report whether the working tree has uncommitted changes."""
        return bool(self._repo.status())

    def exec(self, *args: str) -> bytes:
        """Embedded backends do not expose command execution."""
        del args
        raise operation_not_supported("exec", "embedded")

    def diff(self, from_ref: str, to_ref: str) -> list[DiffEntry]:
        return read.diff(self._repo, from_ref, to_ref)

    def diff_stats(self, from_ref: str, to_ref: str) -> DiffStats:
        return read.diff_stats(self._repo, from_ref, to_ref)

    def status(self) -> list[StatusEntry]:
        return read.status(self._repo)

    def tree_hash(self, revision: str, path: str) -> TreeHash:
        return read.tree_hash(self._repo, revision, path)

    def file_at(self, revision: str, path: str) -> bytes:
        return read.file_at(self._repo, revision, path)

    def list_entries(self, revision: str, path: str) -> list[TreeEntry]:
        return read.list_entries(self._repo, revision, path)

    def log(self, opts: LogOptions | None = None) -> list[Commit]:
        return read.log(self._repo, opts)

    def merge_base(self, a: str, b: str) -> Oid:
        return read.merge_base(self._repo, a, b)

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        return read.is_ancestor(self._repo, ancestor, descendant)

    def blame(self, revision: str, path: str, opts: BlameOptions | None = None) -> list[BlameLine]:
        return read.blame(self._repo, revision, path, opts)

    def describe(self, opts: DescribeOptions | None = None) -> str:
        return read.describe(self._repo, opts)

    def rev_parse(self, revision: str) -> Oid:
        return read.rev_parse(self._repo, revision)

    def grep(self, pattern: str, revision: str, opts: GrepOptions | None = None) -> list[GrepMatch]:
        return read.grep(self._repo, pattern, revision, opts)

    def show(self, object_spec: str) -> bytes:
        return read.show(self._repo, object_spec)

    def stage(self, *paths: str) -> None:
        write.stage(self._repo, *paths)

    def unstage(self, *paths: str) -> None:
        write.unstage(self._repo, *paths)

    def staged_entries(self) -> list[StatusEntry]:
        return write.staged_entries(self._repo)

    def commit(self, message: str, opts: CommitOptions | None = None) -> Oid:
        return write.commit(self._repo, message, opts)

    def merge(self, branch: str, opts: MergeOptions | None = None) -> MergeResult:
        return write.merge(self._repo, branch, opts)

    def abort_merge(self) -> None:
        write.abort_merge(self._repo)

    def rebase(self, onto: str, opts: RebaseOptions | None = None) -> RebaseResult:
        return write.rebase(self._repo, onto, opts)

    def abort_rebase(self) -> None:
        write.abort_rebase(self._repo)

    def continue_rebase(self) -> RebaseResult:
        return write.continue_rebase(self._repo)

    def cherry_pick(self, commit: str, opts: CherryPickOptions | None = None) -> Oid:
        return write.cherry_pick(self._repo, commit, opts)

    def cherry_pick_continue(self) -> Oid:
        return write.cherry_pick_continue(self._repo)

    def cherry_pick_abort(self) -> None:
        write.cherry_pick_abort(self._repo)

    def reset(self, target: str, mode: ResetMode) -> None:
        write.reset(self._repo, target, mode)

    def checkout(self, ref_name: str, opts: CheckoutOptions | None = None) -> None:
        write.checkout(self._repo, ref_name, opts)

    def checkout_files(self, *paths: str) -> None:
        write.checkout_files(self._repo, *paths)

    def stash(self, message: str) -> Oid:
        return write.stash(self._repo, message)

    def stash_push(self, message: str) -> Oid:
        return self.stash(message)

    def stash_pop(self, index: int = 0) -> None:
        write.stash_pop(self._repo, index)

    def stash_list(self) -> list[StashEntry]:
        return write.stash_list(self._repo)

    def list_branches(self, filter: BranchFilter = BranchFilter.LOCAL) -> list[Branch]:
        return manage.list_branches(self._repo, filter)

    def list_tags(self) -> list[Tag]:
        return manage.list_tags(self._repo)

    def create_branch(self, name: str, target: str) -> None:
        manage.create_branch(self._repo, name, target)

    def delete_branch(self, name: str) -> None:
        manage.delete_branch(self._repo, name)

    def create_tag(self, name: str, target: str, message: str) -> None:
        manage.create_tag(self._repo, name, target, message)

    def delete_tag(self, name: str) -> None:
        manage.delete_tag(self._repo, name)

    def list_remotes(self) -> list[Remote]:
        return manage.list_remotes(self._repo)

    def fetch(self, remote: str, opts: FetchOptions | None = None) -> None:
        manage.fetch(self._repo, remote, opts)

    def push(self, remote: str, opts: PushOptions | None = None) -> None:
        manage.push(self._repo, remote, opts)

    def tracking_branch(self, branch: str) -> str:
        return manage.tracking_branch(self._repo, branch)

    def config_get(self, key: str) -> str:
        return manage.config_get(self._repo, key)

    def config_get_all(self, key: str) -> list[str]:
        return manage.config_get_all(self._repo, key)

    def config_set(self, key: str, value: str) -> None:
        manage.config_set(self._repo, key, value)

    def gc(self) -> None:
        manage.gc(self._repo)

    def prune(self) -> None:
        manage.prune(self._repo)

    def fsck(self) -> None:
        manage.fsck(self._repo)

    def clean(self, opts: CleanOptions | None = None) -> list[str]:
        return manage.clean(self._repo, opts)


def init(path: str | Path) -> Backend:
    """Initialize a new git repository at the given path."""
    abs_path = Path(path).resolve()
    abs_path.mkdir(parents=True, exist_ok=True)
    repo = pygit2.init_repository(str(abs_path), bare=False)
    return Backend(repo, abs_path)


def init_bare(path: str | Path) -> Backend:
    """Initialize a new bare git repository at the given path."""
    abs_path = Path(path).resolve()
    abs_path.mkdir(parents=True, exist_ok=True)
    repo = pygit2.init_repository(str(abs_path), bare=True)
    return Backend(repo, abs_path)


def open(path: str | Path) -> Backend:
    """Open a git repository at the given path."""
    abs_path = Path(path).resolve()
    try:
        repo = pygit2.Repository(str(abs_path))
    except pygit2.GitError as exc:
        raise repo_not_found(str(abs_path)) from exc
    root = Path(repo.workdir) if repo.workdir else abs_path
    return Backend(repo, root.resolve())


def discover(path: str | Path) -> Backend:
    """Discover a git repository by walking up from the given path."""
    abs_path = Path(path).resolve()
    try:
        repo_path = pygit2.discover_repository(str(abs_path))
    except pygit2.GitError as exc:
        raise repo_not_found(str(abs_path)) from exc
    if repo_path is None:
        raise repo_not_found(str(abs_path))
    try:
        repo = pygit2.Repository(repo_path)
    except pygit2.GitError as exc:
        raise repo_not_found(str(abs_path)) from exc
    root = Path(repo.workdir) if repo.workdir else abs_path
    return Backend(repo, root.resolve())


def clone(url: str, path: str | Path) -> Backend:
    """Clone a repository into a local path."""
    abs_path = Path(path).resolve()
    try:
        repo = pygit2.clone_repository(url, str(abs_path))
    except pygit2.GitError as exc:
        raise network_error(exc) from exc
    root = Path(repo.workdir) if repo.workdir else abs_path
    return Backend(repo, root.resolve())


def reference_from_pygit2(ref: pygit2.Reference) -> Reference:
    """Convert a pygit2 reference to our Reference type."""
    name = ref.name
    try:
        target = Oid(sha=str(ref.target))
    except (KeyError, TypeError, ValueError) as exc:
        raise ref_not_found(name) from exc
    is_branch = name.startswith("refs/heads/")
    is_tag = name.startswith("refs/tags/")
    return Reference(name=name, target=target, is_branch=is_branch, is_tag=is_tag)
