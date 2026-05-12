"""ConfigReader protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ConfigReader(Protocol):
    """Repository configuration operations."""

    def config_get(self, key: str) -> str:
        """Return a single config value."""
        ...

    def config_get_all(self, key: str) -> list[str]:
        """Return all config values for a key."""
        ...

    def config_set(self, key: str, value: str) -> None:
        """Set a config value."""
        ...
