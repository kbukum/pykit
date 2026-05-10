"""Subprocess-backed git command runner."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SubprocessExecutor:
    """Executes git commands in a working directory."""

    cwd: Path

    def exec(self, *args: str) -> bytes:
        """Run a git command and return raw stdout bytes.

        Raises internal_error on non-zero exit instead of CalledProcessError.
        """
        result = subprocess.run(
            ["git", *args],
            cwd=self.cwd,
            capture_output=True,
        )
        if result.returncode != 0:
            from pykit_git.errors import internal_error

            exc = subprocess.CalledProcessError(
                result.returncode, ["git", *args], output=result.stdout, stderr=result.stderr
            )
            raise internal_error(exc) from exc
        return result.stdout

    def run(self, *args: str) -> subprocess.CompletedProcess[bytes]:
        """Run a git command, returning the full completed process."""
        return subprocess.run(
            ["git", *args],
            cwd=self.cwd,
            capture_output=True,
        )
