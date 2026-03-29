"""Subprocess execution with process-group isolation and SIGTERM→SIGKILL shutdown."""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import time

from pykit_errors import TimeoutError as ProcessTimeoutError
from pykit_process.types import Command, ProcessConfig, ProcessResult

_DEFAULT_CONFIG = ProcessConfig()


async def run_command(command: Command, config: ProcessConfig | None = None) -> ProcessResult:
    """Execute a command as a subprocess with timeout and signal handling.

    Creates the process in its own process group. On timeout, sends SIGTERM
    to the process group, waits for the grace period, then sends SIGKILL.
    """
    cfg = config or _DEFAULT_CONFIG

    if not command.program:
        raise ValueError("command program must not be empty")

    env = None
    if command.env is not None:
        env = {**os.environ, **command.env}

    stdin_pipe = asyncio.subprocess.PIPE if command.stdin_data is not None else None
    stdout_pipe = asyncio.subprocess.PIPE if cfg.capture_output else None
    stderr_pipe = asyncio.subprocess.PIPE if cfg.capture_output else None

    start = time.monotonic()
    proc = await asyncio.create_subprocess_exec(
        command.program,
        *command.args,
        stdin=stdin_pipe,
        stdout=stdout_pipe,
        stderr=stderr_pipe,
        env=env,
        cwd=command.cwd,
        start_new_session=True,
    )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(input=command.stdin_data),
            timeout=cfg.timeout,
        )
    except TimeoutError:
        await _terminate_process(proc, cfg.grace_period)
        raise ProcessTimeoutError(command.display(), cfg.timeout) from None

    elapsed = time.monotonic() - start
    return ProcessResult(
        exit_code=proc.returncode or 0,
        stdout=(stdout_bytes or b"").decode(errors="replace"),
        stderr=(stderr_bytes or b"").decode(errors="replace"),
        duration=elapsed,
        command=command.display(),
    )


async def run_shell(cmd: str, config: ProcessConfig | None = None) -> ProcessResult:
    """Execute a shell command string with timeout and signal handling."""
    cfg = config or _DEFAULT_CONFIG

    if not cmd:
        raise ValueError("shell command must not be empty")

    stdout_pipe = asyncio.subprocess.PIPE if cfg.capture_output else None
    stderr_pipe = asyncio.subprocess.PIPE if cfg.capture_output else None

    start = time.monotonic()
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=stdout_pipe,
        stderr=stderr_pipe,
        start_new_session=True,
    )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=cfg.timeout,
        )
    except TimeoutError:
        await _terminate_process(proc, cfg.grace_period)
        raise ProcessTimeoutError(cmd, cfg.timeout) from None

    elapsed = time.monotonic() - start
    return ProcessResult(
        exit_code=proc.returncode or 0,
        stdout=(stdout_bytes or b"").decode(errors="replace"),
        stderr=(stderr_bytes or b"").decode(errors="replace"),
        duration=elapsed,
        command=cmd,
    )


async def _terminate_process(proc: asyncio.subprocess.Process, grace_period: float) -> None:
    """Send SIGTERM to the process group, then SIGKILL after grace period."""
    pid = proc.pid
    if pid is None:
        return

    try:
        pgid = os.getpgid(pid)
        os.killpg(pgid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return

    try:
        await asyncio.wait_for(proc.wait(), timeout=grace_period)
    except TimeoutError:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(pgid, signal.SIGKILL)
        try:
            await asyncio.wait_for(proc.wait(), timeout=1.0)
        except TimeoutError:
            proc.kill()
