"""Shared types for git operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class FileStatus(StrEnum):
    """How a file changed in a diff."""

    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"
    COPIED = "copied"
    UNTRACKED = "untracked"
    IGNORED = "ignored"
    TYPE_CHANGED = "type_changed"
    CONFLICTED = "conflicted"


class EntryState(StrEnum):
    """A file's state in the working tree or index."""

    STAGED = "staged"
    UNSTAGED = "unstaged"
    UNTRACKED = "untracked"
    CONFLICTED = "conflicted"


class EntryKind(StrEnum):
    """Type of a tree entry."""

    BLOB = "blob"
    TREE = "tree"
    SUBMODULE = "submodule"


class BranchFilter(StrEnum):
    """Controls which branches to list."""

    LOCAL = "local"
    REMOTE = "remote"
    ALL = "all"


class ResetMode(StrEnum):
    """Reset mode for repository state changes."""

    SOFT = "soft"
    MIXED = "mixed"
    HARD = "hard"


@dataclass(frozen=True)
class Oid:
    """Git object ID (SHA-1 or SHA-256 hash)."""

    sha: str

    def is_zero(self) -> bool:
        """Report whether this is the zero OID (all-zero hex string of exactly 40 or 64 chars)."""
        return len(self.sha) in (40, 64) and all(char == "0" for char in self.sha)

    def __str__(self) -> str:
        return self.sha


TreeHash = Oid


@dataclass(frozen=True)
class Signature:
    """Author or committer identity."""

    name: str
    email: str
    when: datetime


@dataclass(frozen=True)
class Reference:
    """A git reference (branch, tag, or HEAD)."""

    name: str
    target: Oid
    is_branch: bool = False
    is_tag: bool = False


@dataclass(frozen=True)
class Commit:
    """A git commit object."""

    oid: Oid
    author: Signature
    committer: Signature
    message: str
    parents: tuple[Oid, ...] = ()


@dataclass(frozen=True)
class DiffEntry:
    """A single file change between two refs."""

    path: str
    old_oid: Oid | None
    new_oid: Oid | None
    status: FileStatus
    old_path: str | None = None


@dataclass(frozen=True)
class DiffStats:
    """Aggregated diff statistics."""

    additions: int = 0
    deletions: int = 0
    files_changed: int = 0


@dataclass(frozen=True)
class StatusEntry:
    """A file's status in the working tree."""

    path: str
    state: EntryState


@dataclass(frozen=True)
class TreeEntry:
    """An entry within a git tree object."""

    name: str
    oid: Oid
    kind: EntryKind
    filemode: int


@dataclass(frozen=True)
class Branch:
    """Branch metadata."""

    name: str
    target: Oid
    upstream: str | None = None


@dataclass(frozen=True)
class Tag:
    """Tag metadata."""

    name: str
    target: Oid
    tagger: Signature | None = None
    message: str = ""


@dataclass(frozen=True)
class Remote:
    """Remote repository metadata."""

    name: str
    url: str
    fetch_specs: tuple[str, ...] = ()
    push_specs: tuple[str, ...] = ()


@dataclass(frozen=True)
class BlameLine:
    """Line-level attribution from git blame."""

    line: int
    commit_oid: Oid
    author: Signature
    content: str


@dataclass(frozen=True)
class GrepMatch:
    """A textual match returned from repository grep."""

    path: str
    line: int
    column: int
    content: str


@dataclass(frozen=True)
class StashEntry:
    """A single stash list entry."""

    index: int
    message: str
    oid: Oid | None = None
    branch: str | None = None


@dataclass(frozen=True)
class MergeResult:
    """Summary of a merge operation."""

    merged: bool = False
    head: Oid | None = None
    fast_forward: bool = False
    conflicts: tuple[str, ...] = ()


@dataclass(frozen=True)
class RebaseResult:
    """Summary of a rebase operation."""

    complete: bool = True
    head: Oid | None = None
    applied: int = 0
    conflicts: tuple[str, ...] = ()
