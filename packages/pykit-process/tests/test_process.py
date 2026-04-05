"""Tests for pykit-process using real subprocesses."""

from __future__ import annotations

import asyncio
import os
import sys

import pytest

from pykit_errors import TimeoutError
from pykit_process import Command, ProcessConfig, ProcessResult, run_command, run_shell

# ---------------------------------------------------------------------------
# Basic execution
# ---------------------------------------------------------------------------


async def test_run_command_echo_hello():
    result = await run_command(Command(program="echo", args=["hello"]))
    assert result.success
    assert result.stdout.strip() == "hello"
    assert result.exit_code == 0


async def test_run_command_true_success():
    result = await run_command(Command(program="true"))
    assert result.exit_code == 0
    assert result.success is True


async def test_run_command_false_failure():
    result = await run_command(Command(program="false"))
    assert result.exit_code != 0
    assert result.success is False


async def test_run_command_captures_stderr_separately():
    result = await run_command(
        Command(
            program=sys.executable,
            args=["-c", "import sys; sys.stdout.write('out\\n'); sys.stderr.write('err\\n')"],
        )
    )
    assert result.success
    assert "out" in result.stdout
    assert "err" in result.stderr
    assert "err" not in result.stdout
    assert "out" not in result.stderr


async def test_run_shell_simple():
    result = await run_shell("echo shell_works")
    assert result.success
    assert "shell_works" in result.stdout


async def test_run_shell_piped_commands():
    result = await run_shell("echo hello | cat")
    assert result.success
    assert result.stdout.strip() == "hello"


async def test_run_shell_chained_commands():
    result = await run_shell("echo first && echo second")
    assert result.success
    lines = result.stdout.strip().splitlines()
    assert lines == ["first", "second"]


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------


async def test_exit_code_zero():
    result = await run_command(Command(program="true"))
    assert result.exit_code == 0
    assert result.success


async def test_exit_code_one():
    result = await run_command(Command(program="false"))
    assert result.exit_code == 1
    assert not result.success


async def test_exit_code_custom_preserved():
    result = await run_command(Command(program="sh", args=["-c", "exit 42"]))
    assert result.exit_code == 42
    assert not result.success


async def test_exit_code_127_command_not_found():
    result = await run_shell("nonexistent_binary_xyz_12345")
    assert result.exit_code == 127


# ---------------------------------------------------------------------------
# Environment & working directory
# ---------------------------------------------------------------------------


async def test_custom_env_vars():
    result = await run_command(
        Command(
            program=sys.executable,
            args=["-c", "import os; print(os.environ['MY_VAR'])"],
            env={"MY_VAR": "42"},
        )
    )
    assert result.success
    assert result.stdout.strip() == "42"


async def test_inherits_parent_env():
    key = "PYKIT_PROCESS_TEST_INHERIT"
    os.environ[key] = "inherited_value"
    try:
        result = await run_command(
            Command(
                program=sys.executable,
                args=["-c", f"import os; print(os.environ.get('{key}', 'MISSING'))"],
            )
        )
        assert result.success
        assert "inherited_value" in result.stdout
    finally:
        del os.environ[key]


async def test_custom_working_directory():
    result = await run_command(Command(program="pwd", cwd="/"))
    assert result.success
    assert result.stdout.strip() == "/"


async def test_nonexistent_working_directory_error():
    with pytest.raises((FileNotFoundError, OSError, NotADirectoryError)):
        await run_command(Command(program="echo", args=["hi"], cwd="/nonexistent_dir_xyz"))


async def test_nonexistent_program_error():
    with pytest.raises((FileNotFoundError, OSError)):
        await run_command(Command(program="nonexistent_binary_xyz_99999"))


# ---------------------------------------------------------------------------
# stdin
# ---------------------------------------------------------------------------


async def test_stdin_data_input():
    result = await run_command(
        Command(
            program=sys.executable,
            args=["-c", "import sys; print(sys.stdin.read())"],
            stdin_data=b"hello stdin",
        )
    )
    assert result.success
    assert "hello stdin" in result.stdout


async def test_stdin_cat():
    result = await run_command(
        Command(program="cat", stdin_data=b"piped through cat")
    )
    assert result.success
    assert result.stdout == "piped through cat"


# ---------------------------------------------------------------------------
# Timeout & signals
# ---------------------------------------------------------------------------


async def test_timeout_kills_process():
    cfg = ProcessConfig(timeout=0.5, grace_period=0.5)
    with pytest.raises(TimeoutError, match="timed out"):
        await run_command(Command(program="sleep", args=["30"]), config=cfg)


async def test_shell_timeout():
    cfg = ProcessConfig(timeout=0.5, grace_period=0.5)
    with pytest.raises(TimeoutError, match="timed out"):
        await run_shell("sleep 30", config=cfg)


async def test_grace_period_sigterm_then_sigkill():
    """Process that traps SIGTERM and ignores it should be SIGKILLed after grace_period."""
    trap_script = (
        "import signal, time; "
        "signal.signal(signal.SIGTERM, lambda *a: None); "
        "time.sleep(60)"
    )
    cfg = ProcessConfig(timeout=0.5, grace_period=0.5)
    with pytest.raises(TimeoutError):
        await run_command(
            Command(program=sys.executable, args=["-c", trap_script]),
            config=cfg,
        )


# ---------------------------------------------------------------------------
# ProcessConfig
# ---------------------------------------------------------------------------


async def test_default_config_values():
    cfg = ProcessConfig()
    assert cfg.timeout == 30.0
    assert cfg.grace_period == 5.0
    assert cfg.capture_output is True


async def test_config_custom_timeout():
    cfg = ProcessConfig(timeout=10.0)
    assert cfg.timeout == 10.0


async def test_config_capture_output_false():
    cfg = ProcessConfig(capture_output=False)
    result = await run_command(
        Command(program="echo", args=["invisible"]),
        config=cfg,
    )
    assert result.success
    assert result.stdout == ""
    assert result.stderr == ""


async def test_config_custom_grace_period():
    cfg = ProcessConfig(grace_period=1.0)
    assert cfg.grace_period == 1.0


# ---------------------------------------------------------------------------
# ProcessResult
# ---------------------------------------------------------------------------


async def test_process_result_success_property():
    success = ProcessResult(exit_code=0, stdout="", stderr="", duration=0.1, command="true")
    failure = ProcessResult(exit_code=1, stdout="", stderr="", duration=0.1, command="false")
    assert success.success is True
    assert failure.success is False


async def test_duration_tracked():
    result = await run_command(Command(program="sleep", args=["0.1"]))
    assert result.success
    assert result.duration >= 0.08  # allow small timing variance


async def test_stdout_stderr_captured():
    result = await run_command(
        Command(
            program=sys.executable,
            args=["-c", "import sys; sys.stdout.write('OUT'); sys.stderr.write('ERR')"],
        )
    )
    assert result.stdout == "OUT"
    assert result.stderr == "ERR"


async def test_command_reference_preserved():
    result = await run_command(Command(program="echo", args=["a", "b"]))
    assert result.command == "echo a b"


async def test_shell_command_reference_preserved():
    result = await run_shell("echo shell_ref")
    assert result.command == "echo shell_ref"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


async def test_empty_command_raises():
    with pytest.raises(ValueError, match="program must not be empty"):
        await run_command(Command(program=""))


async def test_empty_shell_command_raises():
    with pytest.raises(ValueError, match="shell command must not be empty"):
        await run_shell("")


async def test_command_display():
    cmd = Command(program="git", args=["status", "--short"])
    assert cmd.display() == "git status --short"


async def test_command_display_no_args():
    cmd = Command(program="ls")
    assert cmd.display() == "ls"


async def test_very_long_output():
    n = 100_000
    result = await run_command(
        Command(
            program=sys.executable,
            args=["-c", f"print('x' * {n})"],
        )
    )
    assert result.success
    assert len(result.stdout.strip()) == n


async def test_concurrent_subprocess_execution():
    cmds = [
        run_command(Command(program="echo", args=[str(i)]))
        for i in range(10)
    ]
    results = await asyncio.gather(*cmds)
    assert all(r.success for r in results)
    outputs = sorted(r.stdout.strip() for r in results)
    assert outputs == [str(i) for i in range(10)]


async def test_special_characters_in_args():
    result = await run_command(
        Command(program="echo", args=["hello world", "$HOME", "it's", '"quoted"'])
    )
    assert result.success
    assert "hello world" in result.stdout
    assert "$HOME" in result.stdout


async def test_unicode_in_stdout():
    result = await run_command(
        Command(
            program=sys.executable,
            args=["-c", "print('héllo wörld 🎉')"],
        )
    )
    assert result.success
    assert "héllo wörld 🎉" in result.stdout


async def test_unicode_in_stderr():
    result = await run_command(
        Command(
            program=sys.executable,
            args=["-c", "import sys; sys.stderr.write('ërrör 🚨\\n')"],
        )
    )
    assert "ërrör 🚨" in result.stderr


async def test_command_with_empty_args():
    result = await run_command(Command(program="echo"))
    assert result.success
    assert result.stdout.strip() == ""
