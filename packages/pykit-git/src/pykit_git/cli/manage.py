"""CLI management backend."""

from __future__ import annotations

import subprocess
from datetime import datetime

from pykit_git.cli.exec_runner import SubprocessExecutor
from pykit_git.cli.read import _parse_oid
from pykit_git.errors import config_not_found, internal_error, ref_not_found
from pykit_git.options import CleanOptions, FetchOptions, PushOptions
from pykit_git.types import Branch, BranchFilter, Remote, Signature, Tag


class ManageBackend:
    """Management-side CLI backend."""

    _executor: SubprocessExecutor

    def list_branches(self, filter: BranchFilter = BranchFilter.LOCAL) -> list[Branch]:
        args = ["for-each-ref", "--format=%(refname:short)%00%(objectname)%00%(upstream:short)"]
        if filter is BranchFilter.LOCAL:
            args.append("refs/heads")
        elif filter is BranchFilter.REMOTE:
            args.append("refs/remotes")
        else:
            args.extend(["refs/heads", "refs/remotes"])
        output = self._executor.exec(*args).decode(errors="replace")
        branches: list[Branch] = []
        for line in output.splitlines():
            if not line:
                continue
            name, oid_hex, upstream = line.split("\x00")
            branches.append(Branch(name=name, target=_parse_oid(oid_hex), upstream=upstream or None))
        return sorted(branches, key=lambda branch: branch.name)

    def list_tags(self) -> list[Tag]:
        output = self._executor.exec(
            "for-each-ref",
            "-z",
            "refs/tags",
            "--format=%(refname:short)%x1f%(objecttype)%x1f%(objectname)%x1f%(*objectname)%x1f%(taggername)%x1f%(taggeremail)%x1f%(taggerdate:iso-strict)%x1f%(contents)%x00",
        )
        tags: list[Tag] = []
        for raw_record in output.split(b"\x00"):
            if not raw_record:
                continue
            record = raw_record.decode(errors="replace")
            name, object_type, object_oid, peeled_oid, tagger_name, tagger_email, tagger_date, message = (
                record.split("\x1f", 7)
            )
            tagger = None
            if object_type == "tag" and tagger_name and tagger_date:
                tagger = Signature(
                    name=tagger_name,
                    email=tagger_email.strip("<>"),
                    when=datetime.fromisoformat(tagger_date),
                )
            tags.append(
                Tag(
                    name=name,
                    target=_parse_oid(peeled_oid or object_oid),
                    tagger=tagger,
                    message=message.strip() if object_type == "tag" else "",
                )
            )
        return tags

    def create_branch(self, name: str, target: str) -> None:
        self._executor.exec("branch", name, target)

    def delete_branch(self, name: str) -> None:
        result = self._executor.run("branch", "-d", name)
        if result.returncode != 0:
            raise ref_not_found(name)

    def create_tag(self, name: str, target: str, message: str) -> None:
        if message:
            self._executor.exec("tag", "-a", name, target, "-m", message)
            return
        self._executor.exec("tag", name, target)

    def delete_tag(self, name: str) -> None:
        result = self._executor.run("tag", "-d", name)
        if result.returncode != 0:
            raise ref_not_found(name)

    def list_remotes(self) -> list[Remote]:
        output = self._executor.exec("remote", "-v").decode(errors="replace")
        urls: dict[str, str] = {}
        for line in output.splitlines():
            if not line:
                continue
            name, rest = line.split("\t", 1)
            url, _, _kind = rest.partition(" ")
            urls.setdefault(name, url)
        remotes = [
            Remote(
                name=name,
                url=url,
                fetch_specs=tuple(self.config_get_all(f"remote.{name}.fetch")),
                push_specs=tuple(self.config_get_all(f"remote.{name}.push")),
            )
            for name, url in urls.items()
        ]
        return sorted(remotes, key=lambda remote: remote.name)

    def fetch(self, remote: str, opts: FetchOptions | None = None) -> None:
        options = opts or FetchOptions()
        args = ["fetch"]
        if options.prune:
            args.append("--prune")
        if options.depth is not None:
            args.extend(["--depth", str(options.depth)])
        args.extend(options.extra_args)
        args.append(remote)
        args.extend(options.refspecs)
        self._executor.exec(*args)

    def push(self, remote: str, opts: PushOptions | None = None) -> None:
        options = opts or PushOptions()
        args = ["push"]
        if options.force:
            args.append("--force")
        args.extend(options.extra_args)
        args.append(remote)
        args.extend(options.refspecs)
        self._executor.exec(*args)

    def tracking_branch(self, branch: str) -> str:
        remote = self.config_get(f"branch.{branch}.remote")
        merge = self.config_get(f"branch.{branch}.merge")
        short = merge.removeprefix("refs/heads/")
        if not short:
            raise ref_not_found(f"{branch}@{{upstream}}")
        return f"{remote}/{short}"

    def config_get(self, key: str) -> str:
        result = self._executor.run("config", "--get", key)
        if result.returncode != 0:
            raise config_not_found(key)
        return result.stdout.decode(errors="replace").strip()

    def config_get_all(self, key: str) -> list[str]:
        result = self._executor.run("config", "--get-all", key)
        if result.returncode != 0:
            return []
        return [line for line in result.stdout.decode(errors="replace").splitlines() if line]

    def config_set(self, key: str, value: str) -> None:
        self._executor.exec("config", key, value)

    def gc(self) -> None:
        self._executor.exec("gc")

    def prune(self) -> None:
        self._executor.exec("prune")

    def fsck(self) -> None:
        self._executor.exec("fsck")

    def clean(self, opts: CleanOptions | None = None) -> list[str]:
        options = opts or CleanOptions()
        args = ["clean"]
        if options.directories:
            args.append("-d")
        if options.ignored:
            args.append("-x")
        args.append("-f" if options.force else "-n")
        args.extend(options.extra_args)
        result = self._executor.run(*args)
        if result.returncode != 0:
            exc = subprocess.CalledProcessError(
                result.returncode, ["git", *args], output=result.stdout, stderr=result.stderr
            )
            raise internal_error(exc) from exc
        cleaned: list[str] = []
        for line in result.stdout.decode(errors="replace").splitlines():
            if line.startswith("Removing "):
                cleaned.append(line.removeprefix("Removing "))
            elif line.startswith("Would remove "):
                cleaned.append(line.removeprefix("Would remove "))
            elif line:
                cleaned.append(line)
        return cleaned
