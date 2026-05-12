# pykit-process

Subprocess execution with timeout, signal handling, and graceful two-phase termination.

## Installation

```bash
pip install pykit-process
# or
uv add pykit-process
```

## Quick Start

```python
from pykit_process import Command, ProcessConfig, run_command, run_shell

# Run a structured command
cmd = Command(program="ls", args=["-la", "/tmp"], cwd="/home")
result = await run_command(cmd)
print(result.stdout)
print(f"exit={result.exit_code}, duration={result.duration:.2f}s")

# Run a shell command with custom timeout
result = await run_shell("echo hello && sleep 1", ProcessConfig(timeout=10.0))
assert result.success

# Timeout triggers SIGTERM → grace period → SIGKILL
config = ProcessConfig(timeout=5.0, grace_period=2.0)
result = await run_command(Command(program="long-task"), config)
```

## Key Components

- **Command** — Frozen dataclass describing a subprocess invocation (program, args, env, cwd, stdin_data)
- **ProcessConfig** — Configuration for timeout (default 30s), grace period (default 5s), and output capture
- **ProcessResult** — Execution result with exit_code, stdout, stderr, duration, and `success` property
- **run_command()** — Execute a structured command with timeout and signal handling
- **run_shell()** — Execute a shell command string with the same timeout/signal handling

## Dependencies

- `pykit-errors`

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
