"""pygit2 write-side helpers."""

from __future__ import annotations

from pathlib import Path

import pygit2

from pykit_git.errors import internal_error, operation_not_supported
from pykit_git.options import CheckoutOptions, CherryPickOptions, CommitOptions, MergeOptions, RebaseOptions
from pykit_git.types import (
    EntryState,
    MergeResult,
    Oid,
    RebaseResult,
    ResetMode,
    Signature,
    StashEntry,
    StatusEntry,
)


def stage(repo: pygit2.Repository, *paths: str) -> None:
    """Stage one or more paths."""
    index = repo.index
    try:
        for path in paths_to_stage(repo, paths):
            if worktree_path(repo, path).exists():
                index.add(path)
            else:
                remove_from_index(index, path)
        index.write()
    except pygit2.GitError as exc:
        raise internal_error(exc) from exc


def unstage(repo: pygit2.Repository, *paths: str) -> None:
    """Unstage one or more paths."""
    index = repo.index
    try:
        head_commit = repo.head.peel(pygit2.Commit)
    except pygit2.GitError as exc:
        raise internal_error(exc) from exc

    try:
        if not paths:
            index.read_tree(head_commit.tree)
            index.write()
            return
        for path in dict.fromkeys(paths):
            try:
                entry = head_commit.tree[path]
            except KeyError:
                remove_from_index(index, path)
                continue
            index.add(pygit2.IndexEntry(path, entry.id, entry.filemode))
        index.write()
    except pygit2.GitError as exc:
        raise internal_error(exc) from exc


def staged_entries(repo: pygit2.Repository) -> list[StatusEntry]:
    """Return files staged in the index."""
    try:
        head_commit = repo.head.peel(pygit2.Commit)
    except pygit2.GitError as exc:
        raise internal_error(exc) from exc

    entries: list[StatusEntry] = []
    for patch in repo.index.diff_to_tree(head_commit.tree):
        if patch is None:
            continue
        delta = patch.delta
        path = delta.new_file.path or delta.old_file.path or ""
        entries.append(StatusEntry(path=path, state=EntryState.STAGED))
    return sorted(entries, key=lambda entry: entry.path)


def commit(repo: pygit2.Repository, message: str, opts: CommitOptions | None = None) -> Oid:
    """Create a commit from the current index."""
    options = opts or CommitOptions()
    if options.sign:
        raise operation_not_supported("commit(sign=True)", "embedded")

    index = repo.index
    try:
        index.write()
        tree = index.write_tree()
        if options.amend:
            return Oid(sha=str(amend_commit(repo, message, tree, options)))
        author = signature_for_commit(repo, options.author)
        committer = signature_for_commit(repo, options.committer)
        parents = parent_oids(repo)
        oid = repo.create_commit("HEAD", author, committer, message, tree, parents)
    except (KeyError, pygit2.GitError) as exc:
        raise internal_error(exc) from exc
    return Oid(sha=str(oid))


def merge(repo: pygit2.Repository, branch: str, opts: MergeOptions | None = None) -> MergeResult:
    """Embedded merge is not implemented yet."""
    del repo, branch, opts
    raise operation_not_supported("merge", "embedded")


def abort_merge(repo: pygit2.Repository) -> None:
    """Embedded merge abort is not implemented yet."""
    del repo
    raise operation_not_supported("abort_merge", "embedded")


def rebase(repo: pygit2.Repository, onto: str, opts: RebaseOptions | None = None) -> RebaseResult:
    """Embedded rebase is not implemented yet."""
    del repo, onto, opts
    raise operation_not_supported("rebase", "embedded")


def abort_rebase(repo: pygit2.Repository) -> None:
    """Embedded rebase abort is not implemented yet."""
    del repo
    raise operation_not_supported("abort_rebase", "embedded")


def continue_rebase(repo: pygit2.Repository) -> RebaseResult:
    """Embedded rebase continue is not implemented yet."""
    del repo
    raise operation_not_supported("continue_rebase", "embedded")


def cherry_pick(repo: pygit2.Repository, commitish: str, opts: CherryPickOptions | None = None) -> Oid:
    """Embedded cherry-pick is not implemented yet."""
    del repo, commitish, opts
    raise operation_not_supported("cherry_pick", "embedded")


def cherry_pick_continue(repo: pygit2.Repository) -> Oid:
    """Embedded cherry-pick continue is not implemented yet."""
    del repo
    raise operation_not_supported("cherry_pick_continue", "embedded")


def cherry_pick_abort(repo: pygit2.Repository) -> None:
    """Embedded cherry-pick abort is not implemented yet."""
    del repo
    raise operation_not_supported("cherry_pick_abort", "embedded")


def reset(repo: pygit2.Repository, target: str, mode: ResetMode) -> None:
    """Embedded reset is not implemented yet."""
    del repo, target, mode
    raise operation_not_supported("reset", "embedded")


def checkout(repo: pygit2.Repository, ref_name: str, opts: CheckoutOptions | None = None) -> None:
    """Embedded checkout is not implemented yet."""
    del repo, ref_name, opts
    raise operation_not_supported("checkout", "embedded")


def checkout_files(repo: pygit2.Repository, *paths: str) -> None:
    """Embedded checkout-files is not implemented yet."""
    del repo, paths
    raise operation_not_supported("checkout_files", "embedded")


def stash(repo: pygit2.Repository, message: str) -> Oid:
    """Embedded stash is not implemented yet."""
    del repo, message
    raise operation_not_supported("stash", "embedded")


def stash_pop(repo: pygit2.Repository, index: int = 0) -> None:
    """Embedded stash pop is not implemented yet."""
    del repo, index
    raise operation_not_supported("stash_pop", "embedded")


def stash_list(repo: pygit2.Repository) -> list[StashEntry]:
    """Embedded stash list is not implemented yet."""
    del repo
    raise operation_not_supported("stash_list", "embedded")


def amend_commit(
    repo: pygit2.Repository, message: str, tree: pygit2.Oid, options: CommitOptions
) -> pygit2.Oid:
    """Amend the current HEAD commit."""
    head_commit = repo.head.peel(pygit2.Commit)
    author = signature_to_pygit2(options.author) if options.author is not None else None
    committer = signature_for_commit(repo, options.committer)
    return repo.amend_commit(head_commit, "HEAD", author, committer, message, tree)


def parent_oids(repo: pygit2.Repository) -> list[pygit2.Oid]:
    """Return parent OIDs for the next commit."""
    try:
        return [repo.head.target]
    except pygit2.GitError:
        return []


def signature_for_commit(repo: pygit2.Repository, signature: Signature | None) -> pygit2.Signature:
    """Resolve a commit signature from options or repository config."""
    if signature is not None:
        return signature_to_pygit2(signature)
    return repo.default_signature


def signature_to_pygit2(signature: Signature) -> pygit2.Signature:
    """Convert our Signature type to pygit2's Signature."""
    when = signature.when.astimezone()
    offset = when.utcoffset()
    offset_minutes = int(offset.total_seconds() // 60) if offset is not None else 0
    return pygit2.Signature(signature.name, signature.email, int(when.timestamp()), offset_minutes)


def paths_to_stage(repo: pygit2.Repository, paths: tuple[str, ...]) -> list[str]:
    """Resolve explicit or changed paths that should be staged."""
    if paths:
        return list(dict.fromkeys(paths))
    return list(repo.status().keys())


def worktree_path(repo: pygit2.Repository, path: str) -> Path:
    """Return the absolute worktree path for a repository-relative path."""
    root = Path(repo.workdir) if repo.workdir else Path(repo.path).parent
    return root / path


def remove_from_index(index: pygit2.Index, path: str) -> None:
    """Remove a path from the index when present."""
    try:
        index.remove(path)
    except KeyError:
        pass
