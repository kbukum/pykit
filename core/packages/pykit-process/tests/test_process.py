"""Tests for pykit-process using real subprocesses."""

from __future__ import annotations

import asyncio
import os
import sys

import pytest

from pykit_errors import TimeoutError
from pykit_process import Command, ProcessConfig, ProcessResult, run_command


async def test_run_command_echo_hello() -> None:
    result = await run_command(Command(program="echo", args=["hello"]))
    assert result.success
    assert result.stdout.strip() == "hello"


async def test_run_command_true_success() -> None:
    result = await run_command(Command(program="true"))
    assert result.success
    assert result.exit_code == 0


async def test_run_command_false_failure() -> None:
    result = await run_command(Command(program="false"))
    assert not result.success
    assert result.exit_code != 0


async def test_run_command_captures_stderr_separately() -> None:
    result = await run_command(
        Command(
            program=sys.executable,
            args=["-c", "import sys; sys.stdout.write('out\\n'); sys.stderr.write('err\\n')"],
        )
    )
    assert result.stdout.strip() == "out"
    assert result.stderr.strip() == "err"


async def test_custom_exit_code_preserved() -> None:
    result = await run_command(Command(program=sys.executable, args=["-c", "raise SystemExit(42)"]))
    assert result.exit_code == 42


async def test_custom_env_vars() -> None:
    result = await run_command(
        Command(
            program=sys.executable,
            args=["-c", "import os; print(os.environ['MY_VAR'])"],
            env={"MY_VAR": "42"},
        )
    )
    assert result.stdout.strip() == "42"


async def test_scrub_env_removes_inherited_values() -> None:
    key = "PYKIT_PROCESS_TEST_SCRUB"
    os.environ[key] = "secret"
    try:
        result = await run_command(
            Command(
                program=sys.executable,
                args=["-c", f"import os; print(os.environ.get('{key}', 'missing'))"],
            ),
            ProcessConfig(scrub_env=True),
        )
        assert result.stdout.strip() == "missing"
    finally:
        del os.environ[key]


async def test_custom_working_directory() -> None:
    result = await run_command(Command(program="pwd", cwd="/"))
    assert result.stdout.strip() == "/"


async def test_nonexistent_working_directory_error() -> None:
    with pytest.raises((FileNotFoundError, OSError, NotADirectoryError)):
        await run_command(Command(program="echo", args=["hi"], cwd="/nonexistent_dir_xyz"))


async def test_nonexistent_program_error() -> None:
    with pytest.raises((FileNotFoundError, OSError)):
        await run_command(Command(program="nonexistent_binary_xyz_99999"))


async def test_stdin_data_input() -> None:
    result = await run_command(
        Command(
            program=sys.executable,
            args=["-c", "import sys; print(sys.stdin.read())"],
            stdin_data=b"hello stdin",
        )
    )
    assert "hello stdin" in result.stdout


async def test_timeout_kills_process() -> None:
    with pytest.raises(TimeoutError, match="timed out"):
        await run_command(
            Command(program="sleep", args=["30"]),
            config=ProcessConfig(timeout=0.5, grace_period=0.5),
        )


async def test_grace_period_sigterm_then_sigkill() -> None:
    trap_script = "import signal, time; signal.signal(signal.SIGTERM, lambda *a: None); time.sleep(60)"
    with pytest.raises(TimeoutError):
        await run_command(
            Command(program=sys.executable, args=["-c", trap_script]),
            config=ProcessConfig(timeout=0.5, grace_period=0.5),
        )


async def test_default_config_values() -> None:
    cfg = ProcessConfig()
    assert cfg.timeout == 30.0
    assert cfg.grace_period == 5.0
    assert cfg.capture_output is True
    assert cfg.scrub_env is False
    assert cfg.max_output_bytes is None


async def test_capture_output_false() -> None:
    result = await run_command(
        Command(program="echo", args=["hidden"]),
        config=ProcessConfig(capture_output=False),
    )
    assert result.stdout == ""
    assert result.stderr == ""


async def test_max_output_bytes_limits_capture() -> None:
    result = await run_command(
        Command(program=sys.executable, args=["-c", "print('x' * 1000)"]),
        config=ProcessConfig(max_output_bytes=10),
    )
    assert len(result.stdout.strip()) == 10


async def test_process_result_success_property() -> None:
    success = ProcessResult(exit_code=0, stdout="", stderr="", duration=0.1, command="true")
    failure = ProcessResult(exit_code=1, stdout="", stderr="", duration=0.1, command="false")
    assert success.success is True
    assert failure.success is False


async def test_duration_tracked() -> None:
    result = await run_command(Command(program="sleep", args=["0.1"]))
    assert result.duration >= 0.08


async def test_command_reference_preserved() -> None:
    result = await run_command(Command(program="echo", args=["a", "b"]))
    assert result.command == "echo a b"


async def test_empty_command_raises() -> None:
    with pytest.raises(ValueError, match="program must not be empty"):
        await run_command(Command(program=""))


async def test_command_display() -> None:
    command = Command(program="git", args=["status", "--short"])
    assert command.display() == "git status --short"


async def test_concurrent_subprocess_execution() -> None:
    commands = [run_command(Command(program="echo", args=[str(index)])) for index in range(10)]
    results = await asyncio.gather(*commands)
    assert sorted(result.stdout.strip() for result in results) == [str(index) for index in range(10)]


async def test_special_characters_in_args_are_not_interpreted() -> None:
    result = await run_command(
        Command(
            program=sys.executable,
            args=["-c", "import sys; print(sys.argv[1])", "hello && echo hacked"],
        )
    )
    assert result.stdout.strip() == "hello && echo hacked"


async def test_unicode_output_is_preserved() -> None:
    result = await run_command(Command(program=sys.executable, args=["-c", "print('héllo wörld 🎉')"]))
    assert "héllo wörld 🎉" in result.stdout
