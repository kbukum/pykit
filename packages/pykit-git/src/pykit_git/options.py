"""Option types for git operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pykit_git.types import Signature

ExtraArgs = tuple[str, ...]


@dataclass(frozen=True)
class LogOptions:
    """Controls log traversal."""

    max_count: int | None = None
    path_filter: str | None = None
    author_filter: str | None = None
    since: datetime | None = None
    until: datetime | None = None
    extra_args: ExtraArgs = ()


@dataclass(frozen=True)
class BlameOptions:
    """Controls blame output."""

    start_line: int | None = None
    end_line: int | None = None
    ignore_whitespace: bool = False
    extra_args: ExtraArgs = ()


@dataclass(frozen=True)
class CommitOptions:
    """Controls commit creation."""

    author: Signature | None = None
    committer: Signature | None = None
    sign: bool = False
    amend: bool = False
    extra_args: ExtraArgs = ()


@dataclass(frozen=True)
class FetchOptions:
    """Controls fetch behavior."""

    prune: bool = False
    depth: int | None = None
    refspecs: tuple[str, ...] = ()
    extra_args: ExtraArgs = ()


@dataclass(frozen=True)
class PushOptions:
    """Controls push behavior."""

    force: bool = False
    refspecs: tuple[str, ...] = ()
    extra_args: ExtraArgs = ()


@dataclass(frozen=True)
class DescribeOptions:
    """Controls repository describe output."""

    match: str | None = None
    abbreviated: bool = False
    always: bool = True
    extra_args: ExtraArgs = ()


@dataclass(frozen=True)
class GrepOptions:
    """Controls repository grep behavior."""

    ignore_case: bool = False
    extra_args: ExtraArgs = ()


@dataclass(frozen=True)
class MergeOptions:
    """Controls merge behavior."""

    commit: bool = True
    ff_only: bool = False
    squash: bool = False
    extra_args: ExtraArgs = ()


@dataclass(frozen=True)
class RebaseOptions:
    """Controls rebase behavior."""

    interactive: bool = False
    autosquash: bool = False
    extra_args: ExtraArgs = ()


@dataclass(frozen=True)
class CherryPickOptions:
    """Controls cherry-pick behavior."""

    mainline: int | None = None
    no_commit: bool = False
    extra_args: ExtraArgs = ()


@dataclass(frozen=True)
class CheckoutOptions:
    """Controls checkout behavior."""

    create: bool = False
    force: bool = False
    detach: bool = False
    extra_args: ExtraArgs = ()


@dataclass(frozen=True)
class CleanOptions:
    """Controls repository clean behavior."""

    directories: bool = False
    ignored: bool = False
    force: bool = True
    extra_args: ExtraArgs = ()
