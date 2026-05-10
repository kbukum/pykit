"""CLI read backend."""

from __future__ import annotations

import re
import subprocess

from pykit_git.errors import ambiguous_ref, internal_error, operation_not_supported, ref_not_found
from pykit_git.options import BlameOptions, DescribeOptions, GrepOptions, LogOptions
from pykit_git.types import BlameLine, DiffEntry, DiffStats, GrepMatch, Oid, StatusEntry, TreeEntry, TreeHash


class ReadBackend:
    """Read-side CLI backend."""

    def diff(self, from_ref: str, to_ref: str) -> list[DiffEntry]:
        del from_ref, to_ref
        raise operation_not_supported("diff", "cli")

    def diff_stats(self, from_ref: str, to_ref: str) -> DiffStats:
        del from_ref, to_ref
        raise operation_not_supported("diff_stats", "cli")

    def status(self) -> list[StatusEntry]:
        raise operation_not_supported("status", "cli")

    def tree_hash(self, revision: str, path: str) -> TreeHash:
        del revision, path
        raise operation_not_supported("tree_hash", "cli")

    def file_at(self, revision: str, path: str) -> bytes:
        del revision, path
        raise operation_not_supported("file_at", "cli")

    def list_entries(self, revision: str, path: str) -> list[TreeEntry]:
        del revision, path
        raise operation_not_supported("list_entries", "cli")

    def log(self, opts: LogOptions | None = None):
        del opts
        raise operation_not_supported("log", "cli")

    def merge_base(self, a: str, b: str) -> Oid:
        del a, b
        raise operation_not_supported("merge_base", "cli")

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        del ancestor, descendant
        raise operation_not_supported("is_ancestor", "cli")

    def blame(self, revision: str, path: str, opts: BlameOptions | None = None) -> list[BlameLine]:
        del revision, path, opts
        raise operation_not_supported("blame", "cli")

    def describe(self, opts: DescribeOptions | None = None) -> str:
        options = opts or DescribeOptions()
        args = ["describe", "--tags", *options.extra_args]
        if options.match is not None:
            args.extend(["--match", options.match])
        result = self._executor.run(*args)
        if result.returncode == 0:
            return result.stdout.decode().strip()
        if options.always:
            head = str(self.rev_parse("HEAD"))
            return head[:7] if options.abbreviated else head
        _raise_git_error(result, *args, refname="HEAD")

    def rev_parse(self, revision: str) -> Oid:
        result = self._executor.run("rev-parse", revision)
        if result.returncode != 0:
            _raise_git_error(result, "rev-parse", revision, refname=revision)
        return _parse_oid(result.stdout.decode().strip())

    def grep(self, pattern: str, revision: str, opts: GrepOptions | None = None) -> list[GrepMatch]:
        options = opts or GrepOptions()
        args = ["grep", "-n"]
        if options.ignore_case:
            args.append("-i")
        args.extend(options.extra_args)
        args.extend([pattern, revision])
        result = self._executor.run(*args)
        if result.returncode not in (0, 1):
            _raise_git_error(result, *args, refname=revision)
        regex_flags = re.IGNORECASE if options.ignore_case else 0
        regex = re.compile(pattern, regex_flags)
        matches: list[GrepMatch] = []
        for raw_line in result.stdout.decode().splitlines():
            if not raw_line:
                continue
            match = re.match(
                r"(?:(?P<revision>[^:]+):)?(?P<path>.+?):(?P<line>\d+):(?P<content>.*)", raw_line
            )
            if match is None:
                continue
            content = match.group("content")
            found = regex.search(content)
            column = found.start() + 1 if found is not None else 1
            path = match.group("path")
            if match.group("revision") == revision and path.startswith(f"{revision}:"):
                path = path.removeprefix(f"{revision}:")
            matches.append(
                GrepMatch(path=path, line=int(match.group("line")), column=column, content=content)
            )
        return matches

    def show(self, object: str) -> bytes:
        try:
            return self._executor.exec("show", object)
        except subprocess.CalledProcessError as exc:
            _raise_git_error_from_exception(exc, "show", object)


def _parse_oid(hex_str: str) -> Oid:
    value = hex_str.strip()
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", value):
        raise ValueError(f"invalid git oid: {hex_str!r}")
    return Oid(sha=value)


def _raise_git_error(
    result: subprocess.CompletedProcess[bytes],
    *args: str,
    refname: str | None = None,
) -> None:
    stderr = result.stderr.decode(errors="replace")
    exc = subprocess.CalledProcessError(
        result.returncode, ["git", *args], output=result.stdout, stderr=result.stderr
    )
    if refname is not None:
        if "unknown revision or path not in the working tree" in stderr or "bad revision" in stderr:
            raise ref_not_found(refname) from exc
        if "Needed a single revision" in stderr:
            raise ref_not_found(refname) from exc
        if "ambiguous" in stderr and "unknown revision or path not in the working tree" not in stderr:
            raise ambiguous_ref(refname) from exc
    raise internal_error(exc) from exc


def _raise_git_error_from_exception(
    exc: subprocess.CalledProcessError, *args: str, refname: str | None = None
) -> None:
    result = subprocess.CompletedProcess(
        exc.cmd, exc.returncode, stdout=exc.output or b"", stderr=exc.stderr or b""
    )
    _raise_git_error(result, *args, refname=refname)
