"""Regression tests proving process execution is argv-only, not shell-based."""

from __future__ import annotations

import sys

from pykit_process import Command, run_command


async def test_shell_metacharacters_are_plain_argv() -> None:
    result = await run_command(
        Command(
            program=sys.executable,
            args=["-c", "import sys; print(sys.argv[1])", "safe; echo injected && touch never"],
        )
    )

    assert result.success
    assert result.stdout.strip() == "safe; echo injected && touch never"
