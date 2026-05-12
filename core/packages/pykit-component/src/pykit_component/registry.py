"""Registry for managing component lifecycle with deterministic ordering."""

from __future__ import annotations

import asyncio
import contextlib
import threading
from dataclasses import dataclass

from pykit_component.interfaces import Component, Health, State


@dataclass(slots=True)
class _Entry:
    component: Component
    state: State = State.CREATED


@dataclass(frozen=True)
class StopResult:
    """Detailed result for stopping a single component."""

    name: str
    error: Exception | None


class Registry:
    """Manages component lifecycle with deterministic ordering.

    Components are started in registration order and stopped in reverse order.
    """

    def __init__(self) -> None:
        self._entries: list[_Entry] = []
        self._lookup: dict[str, _Entry] = {}
        self._lock = threading.Lock()
        self._lifecycle_lock = asyncio.Lock()

    def register(self, component: Component) -> None:
        """Add a component.

        Args:
            component: Component to register.

        Raises:
            ValueError: If a component with the same name already exists.
        """
        name = component.name
        with self._lock:
            if name in self._lookup:
                raise ValueError(f"component '{name}' already registered")
            entry = _Entry(component)
            self._entries.append(entry)
            self._lookup[name] = entry

    async def start_all(self) -> None:
        """Start all startable components in registration order.

        Components in ``CREATED``, ``STOPPED``, or ``FAILED`` state are eligible to start.
        A failure rolls back already-started components in reverse order.
        """
        async with self._lifecycle_lock:
            with self._lock:
                entries = list(self._entries)

            started: list[_Entry] = []
            for entry in entries:
                if entry.state == State.RUNNING:
                    continue
                if entry.state not in {State.CREATED, State.STOPPED, State.FAILED}:
                    continue

                self._set_state(entry, State.STARTING)
                try:
                    await entry.component.start()
                except Exception:
                    self._set_state(entry, State.FAILED)
                    await self._rollback_started(started)
                    raise
                except BaseException:
                    self._set_state(entry, State.FAILED)
                    await self._rollback_started(started)
                    raise
                else:
                    self._set_state(entry, State.RUNNING)
                    started.append(entry)

    async def stop_all(self) -> None:
        """Stop all running components in reverse registration order.

        Raises:
            ExceptionGroup: If one or more components fail to stop.
        """
        results = await self.stop_all_detailed()
        errors = [result.error for result in results if result.error is not None]
        if errors:
            raise ExceptionGroup("shutdown errors", errors)

    async def stop_all_detailed(self) -> list[StopResult]:
        """Stop all running components and return per-component results."""
        async with self._lifecycle_lock:
            with self._lock:
                entries = [entry for entry in reversed(self._entries) if entry.state == State.RUNNING]

            results: list[StopResult] = []
            for entry in entries:
                self._set_state(entry, State.STOPPING)
                try:
                    await entry.component.stop()
                except Exception as exc:
                    self._set_state(entry, State.FAILED)
                    results.append(StopResult(name=entry.component.name, error=exc))
                except BaseException:
                    self._set_state(entry, State.RUNNING)
                    raise
                else:
                    self._set_state(entry, State.STOPPED)
                    results.append(StopResult(name=entry.component.name, error=None))
            return results

    async def health_all(self) -> list[Health]:
        """Return health status for every registered component."""
        with self._lock:
            components = [entry.component for entry in self._entries]
        return [await component.health() for component in components]

    def get(self, name: str) -> Component | None:
        """Return a component by name, or ``None``."""
        with self._lock:
            entry = self._lookup.get(name)
            return entry.component if entry else None

    def all(self) -> list[Component]:
        """Return all components in registration order."""
        with self._lock:
            return [entry.component for entry in self._entries]

    def state(self, name: str) -> State | None:
        """Return the current state for a registered component."""
        with self._lock:
            entry = self._lookup.get(name)
            return entry.state if entry else None

    def _set_state(self, entry: _Entry, state: State) -> None:
        with self._lock:
            entry.state = state

    async def _rollback_started(self, started: list[_Entry]) -> None:
        for entry in reversed(started):
            self._set_state(entry, State.STOPPING)
            with contextlib.suppress(Exception):
                await entry.component.stop()
            if self.state(entry.component.name) == State.STOPPING:
                self._set_state(entry, State.STOPPED)
