"""HuggingFace Hub target — upload via huggingface_hub.

Requires: ``pip install huggingface-hub``

Authenticate via ``huggingface-cli login`` or ``HF_TOKEN`` env var.

Example::

    target = HuggingFaceTarget(repo_id="username/dataset-name", private=True)
    result = await target.publish(Path("/tmp/dataset"))
"""

from __future__ import annotations

import logging
from pathlib import Path

from pykit_dataset.target import PublishResult

logger = logging.getLogger(__name__)


class HuggingFaceTarget:
    """Upload a directory to HuggingFace as a dataset."""

    def __init__(
        self,
        repo_id: str,
        private: bool = True,
        batch_size: int = 10,
        batch_delay: float = 2.0,
    ) -> None:
        self._repo_id = repo_id
        self._private = private
        self._batch_size = batch_size
        self._batch_delay = batch_delay

    @property
    def name(self) -> str:
        return f"huggingface:{self._repo_id}"

    async def publish(self, directory: Path, metadata: dict[str, str] | None = None) -> PublishResult:
        """Upload directory to HuggingFace Hub as a dataset repo."""
        import asyncio

        from huggingface_hub import CommitOperationAdd, HfApi

        api = HfApi()
        api.create_repo(repo_id=self._repo_id, repo_type="dataset", private=self._private, exist_ok=True)

        # Collect all files
        all_files = sorted(f for f in directory.rglob("*") if f.is_file())
        logger.info("Uploading %d files to %s", len(all_files), self._repo_id)

        uploaded = 0
        for i in range(0, len(all_files), self._batch_size):
            batch = all_files[i : i + self._batch_size]
            operations = [
                CommitOperationAdd(
                    path_in_repo=str(f.relative_to(directory)),
                    path_or_fileobj=str(f),
                )
                for f in batch
            ]

            api.create_commit(
                repo_id=self._repo_id,
                repo_type="dataset",
                operations=operations,
                commit_message=f"Add batch {i // self._batch_size + 1}",
            )
            uploaded += len(batch)
            logger.info("  Uploaded %d/%d files", uploaded, len(all_files))

            if i + self._batch_size < len(all_files):
                await asyncio.sleep(self._batch_delay)

        location = f"https://huggingface.co/datasets/{self._repo_id}"
        return PublishResult(
            target_name=self.name,
            location=location,
            files_published=len(all_files),
            message=f"Dataset published to {location}",
        )
