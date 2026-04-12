"""Periodic ticker worker that satisfies the Component protocol.

:class:`TickerWorker` runs a user-supplied async callable on a fixed
interval in a background :mod:`asyncio` task.  It integrates with the
bootstrap lifecycle via the :class:`~pykit_component.Component` protocol.

Example::

    async def cleanup() -> None:
        ...

    ticker = TickerWorker("cache-cleanup", interval=30.0, handler=cleanup)
    await ticker.start()
    # ... later ...
    await ticker.stop()
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from typing import Any

from pykit_component import Health, HealthStatus


class TickerWorker:
    """A component that runs a function on a fixed interval.

    Parameters
    ----------
    name:
        Component name for logging and health reporting.
    interval:
        Seconds between ticks.
    handler:
        Async callable invoked on each tick.  If it raises, the worker
        records the error in health but keeps running.
    """

    __slots__ = (
        "_fail_count",
        "_handler",
        "_interval",
        "_last_error",
        "_name",
        "_run_count",
        "_running",
        "_task",
    )

    def __init__(
        self,
        name: str,
        interval: float,
        handler: Callable[[], Awaitable[Any]],
    ) -> None:
        self._name = name
        self._interval = interval
        self._handler = handler
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._run_count = 0
        self._fail_count = 0
        self._last_error: str | None = None

    @property
    def name(self) -> str:
        """Component name."""
        return self._name

    @property
    def run_count(self) -> int:
        """Total completed ticks."""
        return self._run_count

    @property
    def fail_count(self) -> int:
        """Total failed ticks."""
        return self._fail_count

    async def start(self) -> None:
        """Launch the background tick loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        """Cancel the tick loop and wait for it to finish."""
        if not self._running:
            return
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def health(self) -> Health:
        """Return current health status."""
        if not self._running:
            return Health(name=self._name, status=HealthStatus.UNHEALTHY, message="not running")
        if self._last_error is not None:
            return Health(name=self._name, status=HealthStatus.DEGRADED, message=self._last_error)
        msg = "ok" if self._run_count > 0 else ""
        return Health(name=self._name, status=HealthStatus.HEALTHY, message=msg)

    async def _loop(self) -> None:
        """Internal tick loop."""
        try:
            while True:
                await asyncio.sleep(self._interval)
                try:
                    await self._handler()
                    self._run_count += 1
                    self._last_error = None
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self._run_count += 1
                    self._fail_count += 1
                    self._last_error = str(exc)
        except asyncio.CancelledError:
            return
