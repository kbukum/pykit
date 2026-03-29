"""Tests for dataset_loader.py — GenericDatasetLoader."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from pykit_bench.dataset import DatasetManifest
from pykit_bench.dataset_loader import GenericDatasetLoader, _DatasetIterator
from pykit_bench.types import BenchSample

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def dataset_dir(tmp_path: Path) -> Path:
    """Create a minimal dataset on disk."""
    manifest = {
        "name": "test-ds",
        "version": "1.0.0",
        "samples": [
            {"id": "s1", "file": "s1.txt", "label": "positive", "source": "test"},
            {"id": "s2", "file": "s2.txt", "label": "negative", "source": "test"},
        ],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "s1.txt").write_bytes(b"hello")
    (tmp_path / "s2.txt").write_bytes(b"world")
    return tmp_path


@pytest.fixture()
def loader(dataset_dir: Path) -> GenericDatasetLoader[str]:
    return GenericDatasetLoader(dataset_dir, mapper=str)


# ---------------------------------------------------------------------------
# manifest()
# ---------------------------------------------------------------------------


class TestManifest:
    def test_load_manifest(self, loader: GenericDatasetLoader[str]):
        m = loader.manifest()
        assert isinstance(m, DatasetManifest)
        assert m.name == "test-ds"
        assert len(m.samples) == 2

    def test_manifest_not_found(self, tmp_path: Path):
        ldr = GenericDatasetLoader(tmp_path, mapper=str)
        with pytest.raises(FileNotFoundError, match="Manifest not found"):
            ldr.manifest()

    def test_manifest_missing_sample_file(self, tmp_path: Path):
        manifest = {
            "name": "broken",
            "samples": [{"id": "s1", "file": "missing.txt", "label": "x"}],
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        ldr = GenericDatasetLoader(tmp_path, mapper=str)
        with pytest.raises(FileNotFoundError, match="Sample file not found"):
            ldr.manifest()


# ---------------------------------------------------------------------------
# all()
# ---------------------------------------------------------------------------


class TestAll:
    def test_all_returns_bench_samples(self, loader: GenericDatasetLoader[str]):
        samples = loader.all()
        assert len(samples) == 2
        assert all(isinstance(s, BenchSample) for s in samples)

    def test_all_sample_contents(self, loader: GenericDatasetLoader[str]):
        samples = loader.all()
        by_id = {s.id: s for s in samples}
        assert by_id["s1"].input == b"hello"
        assert by_id["s2"].input == b"world"

    def test_all_label_mapping(self, dataset_dir: Path):
        ldr = GenericDatasetLoader(dataset_dir, mapper=str.upper)
        samples = ldr.all()
        labels = {s.id: s.label for s in samples}
        assert labels["s1"] == "POSITIVE"
        assert labels["s2"] == "NEGATIVE"


# ---------------------------------------------------------------------------
# filter()
# ---------------------------------------------------------------------------


class TestFilter:
    def test_filter_returns_new_loader(self, loader: GenericDatasetLoader[str]):
        filtered = loader.filter(predicate=lambda s: s.label == "positive")
        assert filtered is not loader
        assert isinstance(filtered, GenericDatasetLoader)

    def test_filter_applies_predicate(self, loader: GenericDatasetLoader[str]):
        filtered = loader.filter(predicate=lambda s: s.label == "positive")
        samples = filtered.all()
        assert len(samples) == 1
        assert samples[0].id == "s1"

    def test_filter_empty_result(self, loader: GenericDatasetLoader[str]):
        filtered = loader.filter(predicate=lambda s: s.label == "nonexistent")
        samples = filtered.all()
        assert len(samples) == 0


# ---------------------------------------------------------------------------
# pipeline()
# ---------------------------------------------------------------------------


class TestPipeline:
    def test_pipeline_returns_pipeline(self, loader: GenericDatasetLoader[str]):
        from pykit_pipeline import Pipeline

        p = loader.pipeline()
        assert isinstance(p, Pipeline)

    def test_pipeline_iterates_all(self, loader: GenericDatasetLoader[str]):
        p = loader.pipeline()
        it = p.iter()
        loop = asyncio.get_event_loop()
        results = []
        while True:
            val = loop.run_until_complete(it.next())
            if val is None:
                break
            results.append(val)
        assert len(results) == 2


# ---------------------------------------------------------------------------
# _DatasetIterator
# ---------------------------------------------------------------------------


class TestDatasetIterator:
    def test_iterator_returns_all_then_none(self, loader: GenericDatasetLoader[str]):
        it = _DatasetIterator(loader)
        loop = asyncio.get_event_loop()
        results = []
        while True:
            val = loop.run_until_complete(it.next())
            if val is None:
                break
            results.append(val)
        assert len(results) == 2

    def test_iterator_lazy_loading(self, loader: GenericDatasetLoader[str]):
        it = _DatasetIterator(loader)
        assert it._samples is None
        loop = asyncio.get_event_loop()
        loop.run_until_complete(it.next())
        assert it._samples is not None


# ---------------------------------------------------------------------------
# Custom manifest file name
# ---------------------------------------------------------------------------


class TestCustomManifest:
    def test_custom_manifest_file(self, tmp_path: Path):
        manifest = {
            "name": "custom",
            "samples": [{"id": "c1", "file": "c1.bin", "label": "yes"}],
        }
        (tmp_path / "custom.json").write_text(json.dumps(manifest), encoding="utf-8")
        (tmp_path / "c1.bin").write_bytes(b"data")

        ldr = GenericDatasetLoader(tmp_path, mapper=str, manifest_file="custom.json")
        m = ldr.manifest()
        assert m.name == "custom"
        samples = ldr.all()
        assert len(samples) == 1
