"""Kaggle dataset target — upload via kagglehub.

Requires: ``pip install kagglehub``

You must have Kaggle API credentials configured:
  - Either ``~/.kaggle/kaggle.json``
  - Or ``KAGGLE_USERNAME`` + ``KAGGLE_KEY`` environment variables

Example::

    target = KaggleTarget(handle="username/dataset-slug")
    result = await target.publish(Path("/tmp/dataset"))
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pykit_dataset.target import PublishResult

logger = logging.getLogger(__name__)


class KaggleTarget:
    """Upload a directory to Kaggle as a dataset."""

    def __init__(
        self,
        handle: str,
        version_notes: str = "",
        ignore_patterns: list[str] | None = None,
    ) -> None:
        self._handle = handle
        self._version_notes = version_notes
        self._ignore_patterns = ignore_patterns or []

    @property
    def name(self) -> str:
        return f"kaggle:{self._handle}"

    async def publish(self, directory: Path, metadata: dict[str, str] | None = None) -> PublishResult:
        """Upload directory to Kaggle as a dataset."""
        import kagglehub

        logger.info("Uploading to Kaggle: %s", self._handle)

        files = list(directory.rglob("*"))
        file_count = sum(1 for f in files if f.is_file())

        kwargs: dict[str, Any] = {"handle": self._handle, "local_dataset_dir": str(directory)}
        if self._version_notes:
            kwargs["version_notes"] = self._version_notes
        if self._ignore_patterns:
            kwargs["ignore_patterns"] = self._ignore_patterns

        kagglehub.dataset_upload(**kwargs)

        location = f"https://www.kaggle.com/datasets/{self._handle}"
        logger.info("Uploaded %d files to %s", file_count, location)

        return PublishResult(
            target_name=self.name,
            location=location,
            files_published=file_count,
            message=f"Dataset published to {location}",
        )
