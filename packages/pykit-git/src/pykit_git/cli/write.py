"""CLI write backend."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime

from pykit_git.cli.read import _parse_oid
from pykit_git.errors import internal_error, merge_conflict
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


class WriteBackend:
    """Write-side CLI backend."""

    def stage(self, *paths: str) -> None:
        if paths:
            self._executor.exec("add", *paths)
            return
        self._executor.exec("add", "-A")

    def unstage(self, *paths: str) -> None:
        if paths:
            self._executor.exec("restore", "--staged", "--", *paths)
            return
        self._executor.exec("restore", "--staged", ":/")

    def staged_entries(self) -> list[StatusEntry]:
        output = self._executor.exec("diff", "--cached", "--name-status").decode()
        entries: list[StatusEntry] = []
        for line in output.splitlines():
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            path = parts[-1]
            entries.append(StatusEntry(path=path, state=EntryState.STAGED))
        return sorted(entries, key=lambda entry: entry.path)

    def commit(self, message: str, opts: CommitOptions | None = None) -> Oid:
        options = opts or CommitOptions()
        args = ["git", "commit", "-m", message]
        if options.author is not None:
            args.extend(["--author", _format_author(options.author)])
        if options.sign:
            args.append("-S")
        if options.amend:
            args.append("--amend")
        args.extend(options.extra_args)
        env = _commit_env(options)
        try:
            subprocess.run(args, cwd=self._executor.cwd, capture_output=True, check=True, env=env)
        except subprocess.CalledProcessError as exc:
            raise internal_error(exc) from exc
        return self.rev_parse("HEAD")

    def merge(self, branch: str, opts: MergeOptions | None = None) -> MergeResult:
        options = opts or MergeOptions()
        args = ["merge"]
        if not options.commit:
            args.append("--no-commit")
        if options.ff_only:
            args.append("--ff-only")
        if options.squash:
            args.append("--squash")
        args.extend(options.extra_args)
        args.append(branch)
        result = self._executor.run(*args)
        output = (result.stdout + result.stderr).decode(errors="replace")
        head = self.rev_parse("HEAD")
        if result.returncode == 0:
            return MergeResult(merged=True, head=head, fast_forward="fast-forward" in output.lower())
        conflicts = _unmerged_paths(self._executor)
        if conflicts:
            return MergeResult(merged=False, head=head, conflicts=conflicts)
        exc = subprocess.CalledProcessError(
            result.returncode, ["git", *args], output=result.stdout, stderr=result.stderr
        )
        raise internal_error(exc) from exc

    def abort_merge(self) -> None:
        self._executor.exec("merge", "--abort")

    def merge_abort(self) -> None:
        self.abort_merge()

    def rebase(self, onto: str, opts: RebaseOptions | None = None) -> RebaseResult:
        options = opts or RebaseOptions()
        args = ["rebase"]
        if options.interactive:
            args.append("-i")
        if options.autosquash:
            args.append("--autosquash")
        args.extend(options.extra_args)
        args.append(onto)
        result = self._executor.run(*args)
        head = self.rev_parse("HEAD")
        if result.returncode == 0:
            return RebaseResult(complete=True, head=head)
        conflicts = _unmerged_paths(self._executor)
        if conflicts:
            return RebaseResult(complete=False, head=head, conflicts=conflicts)
        exc = subprocess.CalledProcessError(
            result.returncode, ["git", *args], output=result.stdout, stderr=result.stderr
        )
        raise internal_error(exc) from exc

    def abort_rebase(self) -> None:
        self._executor.exec("rebase", "--abort")

    def rebase_abort(self) -> None:
        self.abort_rebase()

    def continue_rebase(self) -> RebaseResult:
        result = self._executor.run("rebase", "--continue")
        head = self.rev_parse("HEAD")
        if result.returncode == 0:
            return RebaseResult(complete=True, head=head)
        conflicts = _unmerged_paths(self._executor)
        if conflicts:
            return RebaseResult(complete=False, head=head, conflicts=conflicts)
        exc = subprocess.CalledProcessError(
            result.returncode,
            ["git", "rebase", "--continue"],
            output=result.stdout,
            stderr=result.stderr,
        )
        raise internal_error(exc) from exc

    def rebase_continue(self) -> RebaseResult:
        return self.continue_rebase()

    def cherry_pick(self, commit: str, opts: CherryPickOptions | None = None) -> Oid:
        options = opts or CherryPickOptions()
        args = ["cherry-pick"]
        if options.mainline is not None:
            args.extend(["-m", str(options.mainline)])
        if options.no_commit:
            args.append("--no-commit")
        args.extend(options.extra_args)
        args.append(commit)
        result = self._executor.run(*args)
        if result.returncode != 0:
            conflicts = _unmerged_paths(self._executor)
            if conflicts:
                raise merge_conflict(conflicts[0])
            exc = subprocess.CalledProcessError(
                result.returncode, ["git", *args], output=result.stdout, stderr=result.stderr
            )
            raise internal_error(exc) from exc
        return self.rev_parse("HEAD")

    def cherry_pick_continue(self) -> Oid:
        self._executor.exec("cherry-pick", "--continue")
        return self.rev_parse("HEAD")

    def cherry_pick_abort(self) -> None:
        self._executor.exec("cherry-pick", "--abort")

    def reset(self, target: str, mode: ResetMode) -> None:
        self._executor.exec("reset", f"--{mode.value}", target)

    def checkout(self, ref_name: str, opts: CheckoutOptions | None = None) -> None:
        options = opts or CheckoutOptions()
        args = ["checkout"]
        if options.force:
            args.append("-f")
        if options.detach:
            args.append("--detach")
        if options.create:
            args.extend(["-b", ref_name])
        else:
            args.append(ref_name)
        args.extend(options.extra_args)
        self._executor.exec(*args)

    def checkout_files(self, *paths: str) -> None:
        self._executor.exec("checkout", "--", *paths)

    def stash(self, message: str) -> Oid:
        self._executor.exec("stash", "push", "-m", message)
        return self.rev_parse("stash@{0}")

    def stash_push(self, message: str) -> Oid:
        return self.stash(message)

    def stash_pop(self, index: int = 0) -> None:
        args = ["stash", "pop"]
        if index:
            args.append(f"stash@{{{index}}}")
        result = self._executor.run(*args)
        if result.returncode == 0:
            return
        conflicts = _unmerged_paths(self._executor)
        if conflicts:
            raise merge_conflict(conflicts[0])
        exc = subprocess.CalledProcessError(
            result.returncode, ["git", *args], output=result.stdout, stderr=result.stderr
        )
        raise internal_error(exc) from exc

    def stash_list(self) -> list[StashEntry]:
        output = self._executor.exec("stash", "list", "--format=%gd%x00%H%x00%gs").decode()
        entries: list[StashEntry] = []
        for line in output.splitlines():
            if not line:
                continue
            refname, oid_hex, message = line.split("\x00", 2)
            index = int(refname.removeprefix("stash@{").removesuffix("}"))
            entries.append(
                StashEntry(
                    index=index, message=message, oid=_parse_oid(oid_hex), branch=_stash_branch(message)
                )
            )
        return entries


def _commit_env(options: CommitOptions) -> dict[str, str] | None:
    if options.author is None and options.committer is None:
        return None
    env = dict(os.environ)
    if options.author is not None:
        env.update(_signature_env("AUTHOR", options.author))
    if options.committer is not None:
        env.update(_signature_env("COMMITTER", options.committer))
    return env


def _signature_env(prefix: str, signature: Signature) -> dict[str, str]:
    return {
        f"GIT_{prefix}_NAME": signature.name,
        f"GIT_{prefix}_EMAIL": signature.email,
        f"GIT_{prefix}_DATE": _format_git_date(signature.when),
    }


def _format_author(signature: Signature) -> str:
    return f"{signature.name} <{signature.email}>"


def _format_git_date(when: datetime) -> str:
    return when.isoformat()


def _unmerged_paths(executor) -> tuple[str, ...]:
    output = executor.run("diff", "--name-only", "--diff-filter=U")
    return tuple(path for path in output.stdout.decode().splitlines() if path)


def _stash_branch(message: str) -> str | None:
    for prefix in ("On ", "WIP on "):
        if message.startswith(prefix):
            branch, _, _ = message.removeprefix(prefix).partition(":")
            return branch or None
    return None
