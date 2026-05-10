"""pygit2 read-side helpers."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, timezone

import pygit2
from pygit2.enums import BlameFlag, SortMode

from pykit_git.errors import invalid_line_range, path_not_found, ref_not_found
from pykit_git.options import BlameOptions, DescribeOptions, GrepOptions, LogOptions
from pykit_git.types import (
    BlameLine,
    Commit,
    DiffEntry,
    DiffStats,
    EntryKind,
    EntryState,
    FileStatus,
    GrepMatch,
    Oid,
    Signature,
    StatusEntry,
    TreeEntry,
    TreeHash,
)


def diff(repo: pygit2.Repository, from_ref: str, to_ref: str) -> list[DiffEntry]:
    """Return file changes between two refs."""
    from_commit = commit_for_ref(repo, from_ref)
    to_commit = commit_for_ref(repo, to_ref)
    repo_diff = repo.diff(from_commit, to_commit)

    entries: list[DiffEntry] = []
    for patch in repo_diff:
        if patch is None:
            continue
        delta = patch.delta
        status = file_status_from_delta(delta.status)
        old_oid = oid_or_none(delta.old_file.id)
        new_oid = oid_or_none(delta.new_file.id)
        old_path = delta.old_file.path if status in (FileStatus.RENAMED, FileStatus.COPIED) else None
        path = delta.new_file.path or delta.old_file.path or ""
        entries.append(
            DiffEntry(path=path, old_oid=old_oid, new_oid=new_oid, status=status, old_path=old_path)
        )
    return entries


def diff_stats(repo: pygit2.Repository, from_ref: str, to_ref: str) -> DiffStats:
    """Return aggregated statistics for changes between two refs."""
    from_commit = commit_for_ref(repo, from_ref)
    to_commit = commit_for_ref(repo, to_ref)
    repo_diff = repo.diff(from_commit, to_commit)

    additions = 0
    deletions = 0
    files_changed = 0
    for patch in repo_diff:
        if patch is None:
            continue
        _, patch_additions, patch_deletions = patch.line_stats
        additions += patch_additions
        deletions += patch_deletions
        files_changed += 1
    return DiffStats(additions=additions, deletions=deletions, files_changed=files_changed)


def status(repo: pygit2.Repository) -> list[StatusEntry]:
    """Return working tree status entries."""
    return [
        StatusEntry(path=path, state=entry_state_from_flags(flags))
        for path, flags in sorted(repo.status().items(), key=lambda item: item[0])
    ]


def tree_hash(repo: pygit2.Repository, revision: str, path: str) -> TreeHash:
    """Return the tree hash for a revision and path."""
    tree = resolve_tree(repo, revision, path)
    return Oid(sha=str(tree.id))


def file_at(repo: pygit2.Repository, revision: str, path: str) -> bytes:
    """Return file content at a revision."""
    commit = commit_for_ref(repo, revision)
    try:
        entry = commit.tree[path]
    except KeyError as exc:
        raise path_not_found(f"{revision}:{path}") from exc
    blob = repo.get(entry.id)
    if not isinstance(blob, pygit2.Blob):
        raise path_not_found(f"{revision}:{path}")
    return bytes(blob.data)


def list_entries(repo: pygit2.Repository, revision: str, path: str) -> list[TreeEntry]:
    """Return tree entries for a revision and path."""
    tree = resolve_tree(repo, revision, path)
    entries: list[TreeEntry] = []
    for entry in tree:
        entries.append(
            TreeEntry(
                name=entry.name or "",
                oid=Oid(sha=str(entry.id)),
                kind=entry_kind_from_filemode(entry.filemode),
                filemode=entry.filemode,
            )
        )
    return entries


def log(repo: pygit2.Repository, opts: LogOptions | None = None) -> list[Commit]:
    """Return commits from the current history."""
    options = opts or LogOptions()
    try:
        head_target = repo.head.target
    except pygit2.GitError:
        return []
    walker = repo.walk(head_target, SortMode.TOPOLOGICAL | SortMode.TIME)

    commits: list[Commit] = []
    for raw_commit in walker:
        commit = commit_from_pygit2(raw_commit)
        if not matches_log_options(repo, raw_commit, commit, options):
            continue
        commits.append(commit)
        if options.max_count is not None and len(commits) >= options.max_count:
            break
    return commits


def merge_base(repo: pygit2.Repository, a: str, b: str) -> Oid:
    """Return the best common ancestor of two revisions."""
    left = commit_for_ref(repo, a)
    right = commit_for_ref(repo, b)
    try:
        return Oid(sha=str(repo.merge_base(left.id, right.id)))
    except pygit2.GitError as exc:
        raise ref_not_found(f"{a}..{b}") from exc


def is_ancestor(repo: pygit2.Repository, ancestor: str, descendant: str) -> bool:
    """Report whether ancestor is reachable from descendant."""
    ancestor_commit = commit_for_ref(repo, ancestor)
    descendant_commit = commit_for_ref(repo, descendant)
    try:
        return repo.descendant_of(descendant_commit.id, ancestor_commit.id)
    except pygit2.GitError as exc:
        raise ref_not_found(f"{ancestor}..{descendant}") from exc


def blame(
    repo: pygit2.Repository, revision: str, path: str, opts: BlameOptions | None = None
) -> list[BlameLine]:
    """Return line-level attribution for a file."""
    options = opts or BlameOptions()
    commit = commit_for_ref(repo, revision)
    content = file_at(repo, revision, path).decode("utf-8", errors="replace")
    lines = content.splitlines()

    start = options.start_line or 1
    end = options.end_line or len(lines)
    if start < 1 or end < start:
        raise invalid_line_range(start, end)

    flags = BlameFlag.NORMAL
    if options.ignore_whitespace:
        flags |= BlameFlag.IGNORE_WHITESPACE

    try:
        blame_result = repo.blame(
            path,
            flags=flags,
            newest_commit=commit.id,
            min_line=start,
            max_line=end,
        )
    except pygit2.GitError as exc:
        raise path_not_found(f"{revision}:{path}") from exc

    result: list[BlameLine] = []
    for line_number in range(start, min(end, len(lines)) + 1):
        hunk = blame_result.for_line(line_number)
        result.append(
            BlameLine(
                line=line_number,
                commit_oid=Oid(sha=str(hunk.final_commit_id)),
                author=signature_from_pygit2(hunk.final_committer or commit.committer),
                content=lines[line_number - 1],
            )
        )
    return result


def describe(repo: pygit2.Repository, opts: DescribeOptions | None = None) -> str:
    """Describe the current HEAD revision."""
    options = opts or DescribeOptions()
    commit = commit_for_ref(repo, "HEAD")
    for refname in sorted(name for name in repo.references if name.startswith("refs/tags/")):
        ref = repo.lookup_reference(refname)
        if not isinstance(ref.target, pygit2.Oid):
            continue
        target = peel_tag_target(repo, ref.target)
        if str(target) == str(commit.id):
            return ref.shorthand
    if options.abbreviated:
        return str(commit.id)[:7]
    return str(commit.id)


def rev_parse(repo: pygit2.Repository, revision: str) -> Oid:
    """Resolve a revision expression to an OID."""
    obj = revparse_single(repo, revision)
    return Oid(sha=str(obj.id))


def grep(
    repo: pygit2.Repository, pattern: str, revision: str, opts: GrepOptions | None = None
) -> list[GrepMatch]:
    """Search file contents at a revision."""
    options = opts or GrepOptions()
    try:
        regex = re.compile(pattern, re.IGNORECASE if options.ignore_case else 0)
    except re.error as exc:
        msg = f"invalid grep pattern: {pattern!r}"
        raise ValueError(msg) from exc
    tree = commit_for_ref(repo, revision).tree
    matches: list[GrepMatch] = []
    for path, blob in walk_blobs(repo, tree):
        text = bytes(blob.data).decode("utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            found = regex.search(line)
            if found is None:
                continue
            matches.append(GrepMatch(path=path, line=line_number, column=found.start() + 1, content=line))
    return matches


def show(repo: pygit2.Repository, object_name: str) -> bytes:
    """Show a git object or revision spec."""
    if ":" in object_name:
        revision, path = object_name.split(":", 1)
        return file_at(repo, revision, path)
    obj = revparse_single(repo, object_name)
    if isinstance(obj, pygit2.Blob):
        return bytes(obj.data)
    if isinstance(obj, pygit2.Commit):
        return obj.message.encode()
    return str(obj).encode()


def commit_for_ref(repo: pygit2.Repository, refname: str) -> pygit2.Commit:
    """Resolve a ref to a commit."""
    obj = revparse_single(repo, refname)
    try:
        return obj.peel(pygit2.Commit)
    except pygit2.GitError as exc:
        raise ref_not_found(refname) from exc


def revparse_single(repo: pygit2.Repository, revision: str) -> pygit2.Object:
    """Resolve a revision expression."""
    try:
        return repo.revparse_single(revision)
    except (KeyError, pygit2.GitError) as exc:
        raise ref_not_found(revision) from exc


def resolve_tree(repo: pygit2.Repository, revision: str, path: str) -> pygit2.Tree:
    """Resolve a revision and path to a tree."""
    commit = commit_for_ref(repo, revision)
    tree = commit.tree
    if path and path not in {".", "/"}:
        try:
            entry = tree[path]
        except KeyError as exc:
            raise path_not_found(f"{revision}:{path}") from exc
        subtree = repo.get(entry.id)
        if not isinstance(subtree, pygit2.Tree):
            raise path_not_found(f"{revision}:{path}")
        tree = subtree
    return tree


def matches_log_options(
    repo: pygit2.Repository, raw_commit: pygit2.Commit, commit: Commit, opts: LogOptions
) -> bool:
    """Report whether a commit matches log filtering options."""
    committed_at = commit.committer.when
    if opts.since is not None:
        since = opts.since if opts.since.tzinfo is not None else opts.since.replace(tzinfo=UTC)
        if committed_at < since:
            return False
    if opts.until is not None:
        until = opts.until if opts.until.tzinfo is not None else opts.until.replace(tzinfo=UTC)
        if committed_at > until:
            return False
    if opts.author_filter is not None:
        author = f"{commit.author.name} <{commit.author.email}>".casefold()
        if opts.author_filter.casefold() not in author:
            return False
    return opts.path_filter is None or commit_touches_path(repo, raw_commit, opts.path_filter)


def commit_touches_path(repo: pygit2.Repository, commit: pygit2.Commit, path_filter: str) -> bool:
    """Report whether a commit changed a path."""
    if not commit.parents:
        return tree_contains_path(commit.tree, path_filter)
    for parent in commit.parents:
        repo_diff = repo.diff(parent, commit)
        for patch in repo_diff:
            if patch is None:
                continue
            delta = patch.delta
            if path_matches_filter(delta.new_file.path, path_filter) or path_matches_filter(
                delta.old_file.path, path_filter
            ):
                return True
    return False


def path_matches_filter(path: str | None, path_filter: str) -> bool:
    """Report whether a path matches a file or directory filter."""
    if path is None:
        return False
    normalized = path_filter.rstrip("/")
    if not normalized:
        return True
    return path == normalized or path.startswith(f"{normalized}/")


def tree_contains_path(tree: pygit2.Tree, path_filter: str) -> bool:
    """Report whether a tree contains the requested path."""
    normalized = path_filter.rstrip("/")
    if not normalized:
        return True
    try:
        tree[normalized]
    except KeyError:
        return False
    return True


def commit_from_pygit2(commit: pygit2.Commit) -> Commit:
    """Convert a pygit2 commit to our Commit type."""
    return Commit(
        oid=Oid(sha=str(commit.id)),
        author=signature_from_pygit2(commit.author),
        committer=signature_from_pygit2(commit.committer),
        message=commit.message,
        parents=tuple(Oid(sha=str(parent.id)) for parent in commit.parents),
    )


def signature_from_pygit2(signature: pygit2.Signature) -> Signature:
    """Convert a pygit2 signature to our Signature type."""
    tz = timezone(timedelta(minutes=signature.offset))
    when = datetime.fromtimestamp(signature.time, tz=tz)
    return Signature(name=signature.name, email=signature.email, when=when)


def file_status_from_delta(status: int) -> FileStatus:
    """Map pygit2 delta status to FileStatus."""
    mapping = {
        pygit2.GIT_DELTA_ADDED: FileStatus.ADDED,
        pygit2.GIT_DELTA_DELETED: FileStatus.DELETED,
        pygit2.GIT_DELTA_MODIFIED: FileStatus.MODIFIED,
        pygit2.GIT_DELTA_RENAMED: FileStatus.RENAMED,
        pygit2.GIT_DELTA_COPIED: FileStatus.COPIED,
        pygit2.GIT_DELTA_UNTRACKED: FileStatus.UNTRACKED,
        pygit2.GIT_DELTA_IGNORED: FileStatus.IGNORED,
        pygit2.GIT_DELTA_TYPECHANGE: FileStatus.TYPE_CHANGED,
        pygit2.GIT_DELTA_CONFLICTED: FileStatus.CONFLICTED,
    }
    return mapping.get(status, FileStatus.MODIFIED)


def oid_or_none(raw_oid: object) -> Oid | None:
    """Convert a pygit2 OID-like value to our Oid type when non-zero."""
    sha = str(raw_oid)
    if not sha or all(char == "0" for char in sha):
        return None
    return Oid(sha=sha)


def entry_state_from_flags(flags: int) -> EntryState:
    """Map pygit2 status flags to EntryState."""
    if flags & pygit2.GIT_STATUS_CONFLICTED:
        return EntryState.CONFLICTED
    if flags & (
        pygit2.GIT_STATUS_INDEX_NEW
        | pygit2.GIT_STATUS_INDEX_MODIFIED
        | pygit2.GIT_STATUS_INDEX_DELETED
        | pygit2.GIT_STATUS_INDEX_RENAMED
        | pygit2.GIT_STATUS_INDEX_TYPECHANGE
    ):
        return EntryState.STAGED
    if flags & pygit2.GIT_STATUS_WT_NEW:
        return EntryState.UNTRACKED
    return EntryState.UNSTAGED


def entry_kind_from_filemode(mode: int) -> EntryKind:
    """Map git filemode to EntryKind."""
    if mode == 0o040000:
        return EntryKind.TREE
    if mode == 0o160000:
        return EntryKind.SUBMODULE
    return EntryKind.BLOB


def walk_blobs(repo: pygit2.Repository, tree: pygit2.Tree, prefix: str = "") -> list[tuple[str, pygit2.Blob]]:
    """Walk all blobs under a tree."""
    blobs: list[tuple[str, pygit2.Blob]] = []
    for entry in tree:
        path = f"{prefix}/{entry.name}" if prefix else (entry.name or "")
        obj = repo.get(entry.id)
        if isinstance(obj, pygit2.Tree):
            blobs.extend(walk_blobs(repo, obj, path))
            continue
        if isinstance(obj, pygit2.Blob):
            blobs.append((path, obj))
    return blobs


def peel_tag_target(repo: pygit2.Repository, target: pygit2.Oid) -> pygit2.Oid:
    """Peel tag targets when necessary."""
    obj = repo.get(target)
    if isinstance(obj, pygit2.Tag):
        if isinstance(obj.target, pygit2.Oid):
            return obj.target
        return obj.target.id
    return target
