"""Registry for managing component lifecycle with deterministic ordering."""

from __future__ import annotations

from pykit_component.interfaces import Component, Health


class _Entry:
    __slots__ = ("component", "started")

    def __init__(self, component: Component) -> None:
        self.component = component
        self.started = False


class Registry:
    """Manages component lifecycle with deterministic ordering.

    Components are started in registration order and stopped in reverse order.
    """

    def __init__(self) -> None:
        self._entries: list[_Entry] = []
        self._lookup: dict[str, _Entry] = {}

    def register(self, component: Component) -> None:
        """Add a component. Raises ``ValueError`` on duplicate names."""
        name = component.name
        if name in self._lookup:
            raise ValueError(f"component '{name}' already registered")
        entry = _Entry(component)
        self._entries.append(entry)
        self._lookup[name] = entry

    async def start_all(self) -> None:
        """Start all components in registration order."""
        for entry in self._entries:
            await entry.component.start()
            entry.started = True

    async def stop_all(self) -> None:
        """Stop all started components in reverse registration order."""
        errors: list[Exception] = []
        for entry in reversed(self._entries):
            if not entry.started:
                continue
            try:
                await entry.component.stop()
            except Exception as exc:
                errors.append(exc)
            finally:
                entry.started = False
        if errors:
            raise RuntimeError(f"shutdown errors: {errors}")

    async def health_all(self) -> list[Health]:
        """Return health status for every registered component."""
        return [await entry.component.health() for entry in self._entries]

    def get(self, name: str) -> Component | None:
        """Return a component by name, or ``None``."""
        entry = self._lookup.get(name)
        return entry.component if entry else None

    def all(self) -> list[Component]:
        """Return all components in registration order."""
        return [entry.component for entry in self._entries]
