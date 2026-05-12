"""Tests for pykit.bench.dataset module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pykit_bench.dataset import DatasetLoader


@pytest.fixture
def dataset_dir(tmp_path: Path) -> Path:
    """Create a minimal test dataset."""
    ai_dir = tmp_path / "ai"
    human_dir = tmp_path / "human"
    ai_dir.mkdir()
    human_dir.mkdir()

    (ai_dir / "sample1.txt").write_text("AI generated text content here")
    (human_dir / "sample2.txt").write_text("Human written text content here")

    manifest = {
        "name": "test-dataset",
        "version": "1.0.0",
        "samples": [
            {"id": "ai-1", "file": "ai/sample1.txt", "label": "ai_generated", "source": "GPT"},
            {"id": "human-1", "file": "human/sample2.txt", "label": "human", "source": "Wikipedia"},
        ],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    return tmp_path


class TestDatasetLoader:
    def test_load(self, dataset_dir: Path) -> None:
        loader = DatasetLoader(dataset_dir)
        manifest = loader.load()
        assert manifest.name == "test-dataset"
        assert len(manifest.samples) == 2

    def test_load_missing_manifest(self, tmp_path: Path) -> None:
        loader = DatasetLoader(tmp_path)
        with pytest.raises(FileNotFoundError, match="Manifest not found"):
            loader.load()

    def test_load_missing_sample_file(self, tmp_path: Path) -> None:
        manifest = {"name": "bad", "samples": [{"id": "x", "file": "missing.txt", "label": "human"}]}
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        loader = DatasetLoader(tmp_path)
        with pytest.raises(FileNotFoundError, match="Sample file not found"):
            loader.load()

    def test_get_content(self, dataset_dir: Path) -> None:
        loader = DatasetLoader(dataset_dir)
        manifest = loader.load()
        content = loader.get_content(manifest.samples[0])
        assert content == b"AI generated text content here"

    def test_filter_by_label(self, dataset_dir: Path) -> None:
        loader = DatasetLoader(dataset_dir)
        loader.load()
        ai = loader.filter(label="ai_generated")
        assert len(ai) == 1
        assert ai[0].id == "ai-1"

        human = loader.filter(label="human")
        assert len(human) == 1

        all_samples = loader.filter()
        assert len(all_samples) == 2

    def test_manifest_property(self, dataset_dir: Path) -> None:
        loader = DatasetLoader(dataset_dir)
        # Should auto-load
        assert loader.manifest.name == "test-dataset"
