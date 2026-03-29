"""Tests for pykit-process using real subprocesses."""

from __future__ import annotations

import sys

import pytest

from pykit_errors import TimeoutError
from pykit_process import Command, ProcessConfig, ProcessResult, run_command, run_shell


async def test_simple_command():
    result = await run_command(Command(program="echo", args=["hello"]))
    assert result.success
    assert result.stdout.strip() == "hello"
    assert result.exit_code == 0


async def test_command_with_args():
    result = await run_command(Command(program="echo", args=["-n", "foo bar"]))
    assert result.success
    assert result.stdout == "foo bar"


async def test_exit_code_capture():
    result = await run_command(Command(program="false"))
    assert not result.success
    assert result.exit_code != 0


async def test_timeout_handling():
    cfg = ProcessConfig(timeout=0.5, grace_period=0.5)
    with pytest.raises(TimeoutError, match="timed out"):
        await run_command(Command(program="sleep", args=["30"]), config=cfg)


async def test_stderr_capture():
    result = await run_command(
        Command(program=sys.executable, args=["-c", "import sys; sys.stderr.write('oops\\n')"])
    )
    assert result.success
    assert "oops" in result.stderr


async def test_working_directory():
    result = await run_command(Command(program="pwd", cwd="/"))
    assert result.success
    assert result.stdout.strip() == "/"


async def test_shell_mode():
    result = await run_shell("echo hello && echo world")
    assert result.success
    lines = result.stdout.strip().splitlines()
    assert lines == ["hello", "world"]


async def test_process_result_success_property():
    success = ProcessResult(exit_code=0, stdout="", stderr="", duration=0.1, command="true")
    failure = ProcessResult(exit_code=1, stdout="", stderr="", duration=0.1, command="false")
    assert success.success is True
    assert failure.success is False


async def test_duration_tracked():
    result = await run_command(Command(program="sleep", args=["0.1"]))
    assert result.success
    assert result.duration >= 0.1


async def test_env_variable():
    result = await run_command(
        Command(
            program=sys.executable,
            args=["-c", "import os; print(os.environ['MY_VAR'])"],
            env={"MY_VAR": "42"},
        )
    )
    assert result.success
    assert result.stdout.strip() == "42"


async def test_stdin_data():
    result = await run_command(
        Command(
            program=sys.executable,
            args=["-c", "import sys; print(sys.stdin.read())"],
            stdin_data=b"hello stdin",
        )
    )
    assert result.success
    assert "hello stdin" in result.stdout


async def test_empty_program_raises():
    with pytest.raises(ValueError, match="program must not be empty"):
        await run_command(Command(program=""))


async def test_empty_shell_command_raises():
    with pytest.raises(ValueError, match="shell command must not be empty"):
        await run_shell("")


async def test_command_display():
    cmd = Command(program="git", args=["status", "--short"])
    assert cmd.display() == "git status --short"
