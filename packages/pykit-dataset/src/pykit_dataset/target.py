"""Target protocol — publish collected data to a destination.

Targets receive a directory of organized data and publish it
to a remote service (Kaggle, HuggingFace) or local filesystem.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class PublishResult:
    """Result of a target publish operation."""

    target_name: str
    location: str
    files_published: int
    message: str = ""


@runtime_checkable
class Target(Protocol):
    """Protocol for dataset publish targets."""

    @property
    def name(self) -> str:
        """Unique identifier for this target."""
        ...

    async def publish(self, directory: Path, metadata: dict[str, str] | None = None) -> PublishResult:
        """Publish the contents of ``directory`` to the target.

        The directory structure is:
            directory/
            ├── real/       # Label 0 samples
            └── ai/         # Label 1 samples

        Returns a ``PublishResult`` with location and stats.
        """
        ...
