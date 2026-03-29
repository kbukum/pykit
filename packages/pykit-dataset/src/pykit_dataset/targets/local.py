"""Local filesystem target — data is already on disk.

This is a no-op target that just reports the local path.
Useful when the collector's output directory is the final destination.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pykit_dataset.target import PublishResult

logger = logging.getLogger(__name__)


class LocalTarget:
    """Target that simply reports the local directory."""

    @property
    def name(self) -> str:
        return "local"

    async def publish(self, directory: Path, metadata: dict[str, str] | None = None) -> PublishResult:
        """Count files in directory and return result."""
        files = list(directory.rglob("*"))
        file_count = sum(1 for f in files if f.is_file())
        return PublishResult(
            target_name=self.name,
            location=str(directory),
            files_published=file_count,
            message=f"Data saved to {directory}",
        )
