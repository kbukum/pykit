"""Application bootstrap — lifecycle orchestration."""

from __future__ import annotations

import asyncio
import signal
from collections.abc import Awaitable, Callable
from typing import Self

from pykit_bootstrap.config import AppConfig
from pykit_bootstrap.lifecycle import Hook, Lifecycle
from pykit_logging import get_logger, setup_logging

logger = get_logger("pykit_bootstrap")


class App:
    """Async application with managed lifecycle phases.

    Lifecycle (``run``):
        log startup → start hooks → ready check → ready hooks →
        wait for SIGINT/SIGTERM → stop hooks → log shutdown

    For finite CLI tasks use ``run_task`` instead.
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._lifecycle = Lifecycle()
        self._ready_check: Callable[[], Awaitable[None]] | None = None

    # -- properties ----------------------------------------------------------

    @property
    def config(self) -> AppConfig:
        return self._config

    @property
    def lifecycle(self) -> Lifecycle:
        return self._lifecycle

    # -- convenience registration (delegate to lifecycle) --------------------

    def on_start(self, hook: Hook) -> Self:
        self._lifecycle.on_start(hook)
        return self

    def on_ready(self, hook: Hook) -> Self:
        self._lifecycle.on_ready(hook)
        return self

    def on_stop(self, hook: Hook) -> Self:
        self._lifecycle.on_stop(hook)
        return self

    def set_ready_check(self, fn: Callable[[], Awaitable[None]]) -> Self:
        self._ready_check = fn
        return self

    # -- run (long-running service) ------------------------------------------

    async def run(self) -> None:
        """Execute the full service lifecycle, blocking until a signal."""
        self._setup_logging()
        logger.info(
            "Starting application",
            name=self._config.name,
            version=self._config.version,
            env=self._config.env,
        )

        try:
            await self._lifecycle.run_start_hooks()
            await self._run_ready_check()
            await self._lifecycle.run_ready_hooks()

            logger.info("Application ready — waiting for shutdown signal")
            await self._wait_for_signal()
        finally:
            await self._shutdown()

    # -- run_task (finite CLI jobs) ------------------------------------------

    async def run_task(self, fn: Callable[[], Awaitable[None]]) -> None:
        """Run *fn* between start and stop hooks (no signal wait)."""
        self._setup_logging()

        try:
            await self._lifecycle.run_start_hooks()
            await fn()
        finally:
            await self._shutdown()

    # -- internals -----------------------------------------------------------

    def _setup_logging(self) -> None:
        log_format = "console" if self._config.debug else "auto"
        setup_logging(
            level="DEBUG" if self._config.debug else "INFO",
            log_format=log_format,
            service_name=self._config.name,
        )

    async def _run_ready_check(self) -> None:
        if self._ready_check is not None:
            await self._ready_check()

    async def _wait_for_signal(self) -> None:
        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)

        try:
            await stop_event.wait()
        finally:
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.remove_signal_handler(sig)

    async def _shutdown(self) -> None:
        logger.info("Shutting down", name=self._config.name)
        try:
            await asyncio.wait_for(
                self._lifecycle.run_stop_hooks(),
                timeout=self._config.graceful_timeout,
            )
        except TimeoutError:
            logger.error("Graceful shutdown timed out", timeout=self._config.graceful_timeout)
