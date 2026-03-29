"""Local directory source — load data items from disk.

Example::

    source = LocalSource(
        directory=Path("/data/images/real"),
        label=Label.REAL,
        max_items=500,
    )
    async for item in source.fetch():
        print(item.label, len(item.content))
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from pathlib import Path

from pykit_dataset.model import DataItem, Label, MediaType

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}


class LocalSource:
    """Load data items from a local directory."""

    def __init__(
        self,
        directory: Path,
        label: Label,
        media_type: MediaType = MediaType.IMAGE,
        max_items: int | None = None,
        extensions: set[str] | None = None,
    ) -> None:
        self._directory = directory
        self._label = label
        self._media_type = media_type
        self._max_items = max_items
        self._extensions = extensions or IMAGE_EXTENSIONS

    @property
    def name(self) -> str:
        return f"local:{self._directory.name}"

    async def fetch(self) -> AsyncIterator[DataItem]:
        """Yield items from local directory."""
        if not self._directory.exists():
            logger.warning("Directory does not exist: %s", self._directory)
            return

        count = 0
        max_n = self._max_items or float("inf")

        for path in sorted(self._directory.iterdir()):
            if count >= max_n:
                break
            if not path.is_file():
                continue
            if path.suffix.lower() not in self._extensions:
                continue

            try:
                content = path.read_bytes()
                count += 1
                yield DataItem(
                    content=content,
                    label=self._label,
                    media_type=self._media_type,
                    source_name=self.name,
                    extension=path.suffix.lower(),
                    metadata={"path": str(path)},
                )
            except Exception:
                logger.warning("Failed to read %s", path, exc_info=True)

        logger.info("  %s: %d items", self._directory, count)
