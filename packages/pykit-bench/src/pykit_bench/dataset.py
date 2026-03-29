"""Dataset loading for accuracy benchmarking."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from pathlib import Path


class Label(StrEnum):
    """Ground truth labels. Project-specific labels extend this."""

    POSITIVE = "positive"
    NEGATIVE = "negative"


class Sample(BaseModel):
    """A single labeled test sample."""

    id: str
    file: str
    label: str
    source: str = ""
    description: str = ""
    metadata: dict[str, object] = Field(default_factory=dict)


class DatasetManifest(BaseModel):
    """Manifest describing a test dataset."""

    name: str
    version: str = "1.0.0"
    samples: list[Sample]


class DatasetLoader:
    """Load datasets from manifest.json + files on disk."""

    def __init__(self, dataset_dir: Path) -> None:
        self._dir = dataset_dir
        self._manifest: DatasetManifest | None = None

    def load(self) -> DatasetManifest:
        """Load and validate manifest, check files exist."""
        manifest_path = self._dir / "manifest.json"
        if not manifest_path.exists():
            msg = f"Manifest not found: {manifest_path}"
            raise FileNotFoundError(msg)

        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = DatasetManifest.model_validate(data)

        for sample in manifest.samples:
            sample_path = self._dir / sample.file
            if not sample_path.exists():
                msg = f"Sample file not found: {sample_path} (id={sample.id})"
                raise FileNotFoundError(msg)

        self._manifest = manifest
        return manifest

    def get_content(self, sample: Sample) -> bytes:
        """Load sample file content."""
        path = self._dir / sample.file
        return path.read_bytes()

    def filter(self, label: str | None = None) -> list[Sample]:
        """Filter samples by label."""
        if self._manifest is None:
            self.load()
        assert self._manifest is not None
        if label is None:
            return list(self._manifest.samples)
        return [s for s in self._manifest.samples if s.label == label]

    @property
    def manifest(self) -> DatasetManifest:
        if self._manifest is None:
            self.load()
        assert self._manifest is not None
        return self._manifest
