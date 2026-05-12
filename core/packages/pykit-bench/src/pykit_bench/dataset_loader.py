"""Generic dataset loader with pipeline integration.

Provides lazy loading via Pipeline and type-safe label mapping.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, TypeVar

from pykit_bench.dataset import DatasetManifest, Sample
from pykit_bench.types import BenchSample
from pykit_pipeline import Pipeline, PipelineIterator

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

L = TypeVar("L")


class GenericDatasetLoader[L]:
    """Generic dataset loader with label mapping and pipeline support.

    Mirrors gokit's ``bench.DatasetLoader[L]``.
    """

    def __init__(
        self,
        dataset_dir: Path,
        mapper: Callable[[str], L],
        *,
        manifest_file: str = "manifest.json",
    ) -> None:
        self._dir = dataset_dir
        self._mapper = mapper
        self._manifest_file = manifest_file
        self._filter: Callable[[Sample], bool] | None = None

    def manifest(self) -> DatasetManifest:
        """Load and validate the dataset manifest."""
        manifest_path = self._dir / self._manifest_file
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
        return manifest

    def all(self) -> list[BenchSample[L]]:
        """Load all samples into memory."""
        manifest = self.manifest()
        samples: list[BenchSample[L]] = []
        for s in manifest.samples:
            if self._filter and not self._filter(s):
                continue
            label = self._mapper(s.label)
            content = (self._dir / s.file).read_bytes()
            samples.append(
                BenchSample(
                    id=s.id,
                    label=label,
                    input=content,
                    source=s.source,
                    metadata=dict(s.metadata),
                )
            )
        return samples

    def pipeline(self) -> Pipeline[BenchSample[L]]:
        """Return a lazy pipeline over dataset samples."""
        return Pipeline.from_fn(lambda: _DatasetIterator(self))

    def filter(self, predicate: Callable[[Sample], bool]) -> GenericDatasetLoader[L]:
        """Return a new loader with an additional filter."""
        loader = GenericDatasetLoader(
            self._dir,
            self._mapper,
            manifest_file=self._manifest_file,
        )
        loader._filter = predicate
        return loader


class _DatasetIterator[L](PipelineIterator[BenchSample[L]]):
    """Lazy iterator over dataset samples."""

    def __init__(self, loader: GenericDatasetLoader[L]) -> None:
        self._loader = loader
        self._samples: list[BenchSample[L]] | None = None
        self._index = 0

    async def next(self) -> BenchSample[L] | None:
        if self._samples is None:
            self._samples = self._loader.all()
        if self._index >= len(self._samples):
            return None
        sample = self._samples[self._index]
        self._index += 1
        return sample
