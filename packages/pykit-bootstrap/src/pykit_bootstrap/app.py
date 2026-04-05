"""Application bootstrap — lifecycle orchestration."""

from __future__ import annotations

import asyncio
import signal
from collections.abc import Awaitable, Callable
from typing import Self

from pykit_bootstrap.config import AppConfig
from pykit_bootstrap.lifecycle import Hook, Lifecycle
from pykit_component import Component, Registry
from pykit_logging import get_logger, setup_logging

logger = get_logger("pykit_bootstrap")


class App:
    """Async application with managed lifecycle phases.

    Lifecycle (``run``):
        log startup → start components → configure hooks → start hooks →
        ready check → ready hooks → wait for SIGINT/SIGTERM →
        stop hooks → stop components → log shutdown

    For finite CLI tasks use ``run_task`` instead.
    """

    def __init__(self, config: AppConfig, *, graceful_timeout: float = 30.0) -> None:
        self._config = config
        self._graceful_timeout = graceful_timeout
        self._lifecycle = Lifecycle()
        self._registry = Registry()
        self._ready_check: Callable[[], Awaitable[None]] | None = None

    # -- properties ----------------------------------------------------------

    @property
    def config(self) -> AppConfig:
        return self._config

    @property
    def lifecycle(self) -> Lifecycle:
        return self._lifecycle

    @property
    def registry(self) -> Registry:
        return self._registry

    # -- convenience registration (delegate to lifecycle) --------------------

    def with_component(self, component: Component) -> Self:
        """Register a component for lifecycle management."""
        self._registry.register(component)
        return self

    def on_configure(self, hook: Hook) -> Self:
        """Register a hook to run after components start but before start hooks."""
        self._lifecycle.on_configure(hook)
        return self

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
        sc = self._config.service_config
        self._setup_logging()
        logger.info(
            "Starting application",
            name=sc.name,
            version=sc.version,
            env=sc.environment.value,
        )

        try:
            await self._registry.start_all()
            await self._lifecycle.run_configure_hooks()
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
            await self._registry.start_all()
            await self._lifecycle.run_configure_hooks()
            await self._lifecycle.run_start_hooks()
            await fn()
        finally:
            await self._shutdown()

    # -- internals -----------------------------------------------------------

    def _setup_logging(self) -> None:
        sc = self._config.service_config
        if sc.debug:
            level = "DEBUG"
            fmt = "console"
        else:
            level = sc.logging.level
            fmt = sc.logging.format
        setup_logging(level=level, log_format=fmt, service_name=sc.name)

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
        sc = self._config.service_config
        logger.info("Shutting down", name=sc.name)
        try:
            await asyncio.wait_for(
                self._lifecycle.run_stop_hooks(),
                timeout=self._graceful_timeout,
            )
        except TimeoutError:
            logger.error("Graceful shutdown timed out", timeout=self._graceful_timeout)
        finally:
            await self._registry.stop_all()
