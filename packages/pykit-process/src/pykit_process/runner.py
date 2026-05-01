"""Subprocess execution with process-group isolation and bounded output capture."""

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
    """Execute a command as a subprocess with timeout and signal handling."""
    cfg = config or _DEFAULT_CONFIG
    if not command.program:
        raise ValueError("command program must not be empty")

    start = time.monotonic()
    proc = await asyncio.create_subprocess_exec(
        command.program,
        *command.args,
        stdin=asyncio.subprocess.PIPE if command.stdin_data is not None else None,
        stdout=asyncio.subprocess.PIPE if cfg.capture_output else None,
        stderr=asyncio.subprocess.PIPE if cfg.capture_output else None,
        env=_build_env(command, cfg),
        cwd=command.cwd,
        start_new_session=True,
    )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            _communicate(proc, command.stdin_data, cfg.max_output_bytes),
            timeout=cfg.timeout,
        )
    except TimeoutError:
        await _terminate_process(proc, cfg.grace_period)
        raise ProcessTimeoutError(command.display(), cfg.timeout) from None

    return ProcessResult(
        exit_code=proc.returncode or 0,
        stdout=stdout_bytes.decode(errors="replace"),
        stderr=stderr_bytes.decode(errors="replace"),
        duration=time.monotonic() - start,
        command=command.display(),
    )


def _build_env(command: Command, config: ProcessConfig) -> dict[str, str]:
    base = {"PATH": os.environ.get("PATH", "")} if config.scrub_env else dict(os.environ)
    if command.env is not None:
        base.update(command.env)
    return base


async def _communicate(
    proc: asyncio.subprocess.Process,
    stdin_data: bytes | None,
    max_output_bytes: int | None,
) -> tuple[bytes, bytes]:
    stdout_task = asyncio.create_task(_read_stream(proc.stdout, max_output_bytes))
    stderr_task = asyncio.create_task(_read_stream(proc.stderr, max_output_bytes))

    try:
        if proc.stdin is not None:
            if stdin_data is not None:
                proc.stdin.write(stdin_data)
                await proc.stdin.drain()
            proc.stdin.close()
            with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                await proc.stdin.wait_closed()

        await proc.wait()
        return await stdout_task, await stderr_task
    finally:
        for task in (stdout_task, stderr_task):
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task


async def _read_stream(
    stream: asyncio.StreamReader | None,
    max_output_bytes: int | None,
) -> bytes:
    if stream is None:
        return b""

    chunks: list[bytes] = []
    collected = 0
    limit = max_output_bytes

    while True:
        chunk = await stream.read(8192)
        if not chunk:
            return b"".join(chunks)
        if limit is None:
            chunks.append(chunk)
            continue
        if collected >= limit:
            continue
        remaining = limit - collected
        chunks.append(chunk[:remaining])
        collected += min(len(chunk), remaining)


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
