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
        """Run a git command and return raw stdout bytes."""
        result = subprocess.run(
            ["git", *args],
            cwd=self.cwd,
            capture_output=True,
            check=True,
        )
        return result.stdout

    def run(self, *args: str) -> subprocess.CompletedProcess[bytes]:
        """Run a git command, returning the full completed process."""
        return subprocess.run(
            ["git", *args],
            cwd=self.cwd,
            capture_output=True,
        )
