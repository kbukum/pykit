"""Chain operation protocol."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

ProgressFn = Any  # Callable[[int, str | None], None] - see below for runtime signature


@runtime_checkable
class Operation(Protocol):
    """A single step in a sequential chain.

    Each operation receives the output of the previous step (or the initial
    input) and produces an output for the next step.
    """

    @property
    def id(self) -> str:
        """Unique identifier for this operation."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name (may equal id)."""
        ...

    async def execute(self, input: Any, progress: ProgressFn) -> Any:
        """Execute the operation.

        Args:
            input: Output from the previous step (or chain input for step 0).
            progress: Callback ``(percent: int, message: str | None) -> None``
                for reporting completion (0-100).

        Returns:
            Output value for the next step.
        """
        ...

    async def cleanup(self, output: Any) -> None:
        """Called when the chain fails after this operation completed.

        Used to delete intermediate files, release resources, etc.
        The default implementation is a no-op.
        """
        ...
