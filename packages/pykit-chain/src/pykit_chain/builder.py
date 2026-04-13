"""Fluent builder for constructing chain executors."""

from __future__ import annotations

from pykit_chain.executor import ChainConfig, ChainExecutor
from pykit_chain.operation import Operation


class ChainBuilder:
    """Fluent API for constructing chain executors."""

    def __init__(self) -> None:
        self._operations: list[Operation] = []
        self._config = ChainConfig()

    def step(self, operation: Operation) -> ChainBuilder:
        """Add an operation to the chain."""
        self._operations.append(operation)
        return self

    def config(self, cfg: ChainConfig) -> ChainBuilder:
        """Set the full chain configuration."""
        self._config = cfg
        return self

    def cleanup_on_failure(self, enabled: bool) -> ChainBuilder:
        """Enable or disable cleanup of completed steps on failure."""
        self._config.cleanup_on_failure = enabled
        return self

    def stop_on_failure(self, enabled: bool) -> ChainBuilder:
        """Enable or disable stopping on the first failure."""
        self._config.stop_on_failure = enabled
        return self

    def build(self) -> ChainExecutor:
        """Build the chain executor."""
        return ChainExecutor(list(self._operations), self._config)
