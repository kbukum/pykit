"""pygit2 management helpers."""

from __future__ import annotations

import pygit2
from pygit2.enums import BranchType, FetchPrune, ObjectType

from pykit_git.embedded.read import commit_for_ref, signature_from_pygit2
from pykit_git.errors import (
    config_not_found,
    internal_error,
    operation_not_supported,
    ref_not_found,
    remote_not_found,
)
from pykit_git.options import CleanOptions, FetchOptions, PushOptions
from pykit_git.types import Branch, BranchFilter, Oid, Remote, Tag


def list_branches(repo: pygit2.Repository, filter: BranchFilter = BranchFilter.LOCAL) -> list[Branch]:
    """Return repository branches."""
    branches: list[Branch] = []
    for branch in iter_branches(repo, filter):
        upstream = branch.upstream.shorthand if branch.upstream is not None else None
        branches.append(Branch(name=branch.shorthand, target=Oid(sha=str(branch.target)), upstream=upstream))
    return sorted(branches, key=lambda branch: branch.name)


def list_tags(repo: pygit2.Repository) -> list[Tag]:
    """Return repository tags."""
    tags: list[Tag] = []
    for refname in sorted(name for name in repo.references if name.startswith("refs/tags/")):
        ref = repo.lookup_reference(refname)
        tag_obj = repo.get(ref.target)
        tagger = None
        message = ""
        target = ref.target
        if isinstance(tag_obj, pygit2.Tag):
            tagger = signature_from_pygit2(tag_obj.tagger)
            message = tag_obj.message or ""
            target = tag_obj.target
        tags.append(Tag(name=ref.shorthand, target=Oid(sha=str(target)), tagger=tagger, message=message))
    return tags


def create_branch(repo: pygit2.Repository, name: str, target: str) -> None:
    """Create a branch at the given target."""
    commit = commit_for_ref(repo, target)
    try:
        repo.create_branch(name, commit)
    except pygit2.GitError as exc:
        raise internal_error(exc) from exc


def delete_branch(repo: pygit2.Repository, name: str) -> None:
    """Delete a local branch."""
    branch = repo.lookup_branch(name, BranchType.LOCAL)
    if branch is None:
        raise ref_not_found(name)
    try:
        branch.delete()
    except pygit2.GitError as exc:
        raise internal_error(exc) from exc


def create_tag(repo: pygit2.Repository, name: str, target: str, message: str) -> None:
    """Create an annotated tag."""
    commit = commit_for_ref(repo, target)
    try:
        tagger = repo.default_signature
    except KeyError:
        tagger = commit.committer
    try:
        repo.create_tag(name, commit.id, ObjectType.COMMIT, tagger, message)
    except pygit2.GitError as exc:
        raise internal_error(exc) from exc


def delete_tag(repo: pygit2.Repository, name: str) -> None:
    """Delete a tag."""
    try:
        ref = repo.lookup_reference(f"refs/tags/{name}")
    except KeyError as exc:
        raise ref_not_found(name) from exc
    try:
        ref.delete()
    except pygit2.GitError as exc:
        raise internal_error(exc) from exc


def list_remotes(repo: pygit2.Repository) -> list[Remote]:
    """Return configured remotes."""
    remotes = [
        Remote(
            name=remote.name or "",
            url=remote.url or "",
            fetch_specs=tuple(remote.fetch_refspecs),
            push_specs=tuple(remote.push_refspecs),
        )
        for remote in repo.remotes
    ]
    return sorted(remotes, key=lambda remote: remote.name)


def fetch(repo: pygit2.Repository, remote: str, opts: FetchOptions | None = None) -> None:
    """Fetch refs from a configured remote."""
    options = opts or FetchOptions()
    remote_ref = lookup_remote(repo, remote)
    prune = FetchPrune.PRUNE if options.prune else FetchPrune.UNSPECIFIED
    depth = options.depth or 0
    refspecs = list(options.refspecs) or None
    try:
        remote_ref.fetch(refspecs=refspecs, prune=prune, depth=depth)
    except pygit2.GitError as exc:
        raise internal_error(exc) from exc


def push(repo: pygit2.Repository, remote: str, opts: PushOptions | None = None) -> None:
    """Push refs to a configured remote."""
    options = opts or PushOptions()
    remote_ref = lookup_remote(repo, remote)
    refspecs = list(options.refspecs)
    if options.force:
        refspecs = [refspec if refspec.startswith("+") else f"+{refspec}" for refspec in refspecs]
    if not refspecs:
        branch = repo.head.shorthand
        refspecs = [f"refs/heads/{branch}:refs/heads/{branch}"]
    try:
        remote_ref.push(refspecs)
    except pygit2.GitError as exc:
        raise internal_error(exc) from exc


def tracking_branch(repo: pygit2.Repository, branch: str) -> str:
    """Return the upstream branch tracked by the local branch."""
    local_branch = repo.lookup_branch(branch, BranchType.LOCAL)
    if local_branch is None:
        raise ref_not_found(branch)
    try:
        upstream = local_branch.upstream
    except (KeyError, ValueError) as exc:
        raise ref_not_found(f"{branch}@{{upstream}}") from exc
    return upstream.shorthand


def config_get(repo: pygit2.Repository, key: str) -> str:
    """Return a single config value."""
    try:
        return str(repo.config[key])
    except KeyError as exc:
        raise config_not_found(key) from exc


def config_get_all(repo: pygit2.Repository, key: str) -> list[str]:
    """Return all config values for a key."""
    values = [str(value) for value in repo.config.get_multivar(key, ".*")]
    if values:
        return values
    try:
        return [str(repo.config[key])]
    except KeyError:
        return []


def config_set(repo: pygit2.Repository, key: str, value: str) -> None:
    """Set a config value."""
    repo.config[key] = value


def gc(repo: pygit2.Repository) -> None:
    """Embedded gc is not implemented yet."""
    del repo
    raise operation_not_supported("gc", "embedded")


def prune(repo: pygit2.Repository) -> None:
    """Embedded prune is not implemented yet."""
    del repo
    raise operation_not_supported("prune", "embedded")


def fsck(repo: pygit2.Repository) -> None:
    """Embedded fsck is not implemented yet."""
    del repo
    raise operation_not_supported("fsck", "embedded")


def clean(repo: pygit2.Repository, opts: CleanOptions | None = None) -> list[str]:
    """Embedded clean is not implemented yet."""
    del repo, opts
    raise operation_not_supported("clean", "embedded")


def iter_branches(repo: pygit2.Repository, filter: BranchFilter) -> list[pygit2.Branch]:
    """Return pygit2 branch references for the requested filter."""
    if filter is BranchFilter.LOCAL:
        return lookup_branches(repo, BranchType.LOCAL)
    if filter is BranchFilter.REMOTE:
        return lookup_branches(repo, BranchType.REMOTE)
    return lookup_branches(repo, BranchType.LOCAL) + lookup_branches(repo, BranchType.REMOTE)


def lookup_branches(repo: pygit2.Repository, branch_type: BranchType) -> list[pygit2.Branch]:
    """Resolve branch names to pygit2 Branch objects."""
    branches: list[pygit2.Branch] = []
    for name in repo.listall_branches(branch_type):
        branch = repo.lookup_branch(name, branch_type)
        if branch is not None:
            branches.append(branch)
    return branches


def lookup_remote(repo: pygit2.Repository, remote: str) -> pygit2.Remote:
    """Resolve a configured remote by name."""
    try:
        return repo.remotes[remote]
    except KeyError as exc:
        raise remote_not_found(remote) from exc
