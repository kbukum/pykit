"""Data types for subprocess execution."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Command:
    """Subprocess invocation descriptor."""

    program: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None
    cwd: str | None = None
    stdin_data: bytes | None = None

    def display(self) -> str:
        """Human-readable command string."""
        return " ".join([self.program, *self.args])


@dataclass(frozen=True)
class ProcessResult:
    """Result of a subprocess execution."""

    exit_code: int
    stdout: str
    stderr: str
    duration: float
    command: str

    @property
    def success(self) -> bool:
        return self.exit_code == 0


@dataclass(frozen=True)
class ProcessConfig:
    """Configuration for subprocess execution."""

    timeout: float = 30.0
    grace_period: float = 5.0
    capture_output: bool = True
    scrub_env: bool = False
    max_output_bytes: int | None = None
