"""Lifecycle hook management."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

Hook = Callable[[], Awaitable[None]]


class Lifecycle:
    """Manages ordered start, ready, and stop hooks.

    Start and ready hooks execute in registration order.
    Stop hooks execute in **reverse** registration order so that
    resources are torn down in the opposite order they were set up.
    """

    def __init__(self) -> None:
        self._on_start: list[Hook] = []
        self._on_ready: list[Hook] = []
        self._on_stop: list[Hook] = []

    def on_start(self, hook: Hook) -> None:
        """Register a hook to run during the start phase."""
        self._on_start.append(hook)

    def on_ready(self, hook: Hook) -> None:
        """Register a hook to run after the ready check passes."""
        self._on_ready.append(hook)

    def on_stop(self, hook: Hook) -> None:
        """Register a hook to run during shutdown."""
        self._on_stop.append(hook)

    async def run_start_hooks(self) -> None:
        """Run all start hooks in registration order."""
        for hook in self._on_start:
            await hook()

    async def run_ready_hooks(self) -> None:
        """Run all ready hooks in registration order."""
        for hook in self._on_ready:
            await hook()

    async def run_stop_hooks(self) -> None:
        """Run all stop hooks in **reverse** registration order."""
        for hook in reversed(self._on_stop):
            await hook()
