"""Comprehensive tests for pykit-dataset package."""

from __future__ import annotations

import asyncio
import dataclasses
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from pykit_dataset import (
    Collector,
    CollectorConfig,
    CollectorResult,
    DataItem,
    Label,
    MediaType,
    Source,
    Target,
    Transform,
)
from pykit_dataset.collector import MANIFEST_FILE, _load_manifest, _save_manifest, _source_cache_key
from pykit_dataset.sources.local import IMAGE_EXTENSIONS, LocalSource
from pykit_dataset.target import PublishResult
from pykit_dataset.targets.local import LocalTarget
from pykit_dataset.transform import ResizeTransform

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_item(
    content: bytes = b"fake-image-bytes",
    label: Label = Label.REAL,
    media_type: MediaType = MediaType.IMAGE,
    source_name: str = "test-source",
    extension: str = ".jpg",
    metadata: dict[str, str] | None = None,
) -> DataItem:
    return DataItem(
        content=content,
        label=label,
        media_type=media_type,
        source_name=source_name,
        extension=extension,
        metadata=metadata or {},
    )


class StubSource:
    """Minimal Source implementation for testing."""

    def __init__(self, items: list[DataItem] | None = None) -> None:
        self._items = items or []

    @property
    def name(self) -> str:
        return "stub-source"

    async def fetch(self) -> AsyncIterator[DataItem]:
        for item in self._items:
            yield item


class StubTarget:
    """Minimal Target implementation for testing."""

    def __init__(self) -> None:
        self.published_dirs: list[Path] = []

    @property
    def name(self) -> str:
        return "stub-target"

    async def publish(self, directory: Path, metadata: dict[str, str] | None = None) -> PublishResult:
        self.published_dirs.append(directory)
        return PublishResult(
            target_name=self.name,
            location=str(directory),
            files_published=0,
            message="ok",
        )


class StubTransform:
    """Minimal Transform implementation for testing."""

    def __init__(self, suffix: str = "-transformed") -> None:
        self._suffix = suffix

    @property
    def name(self) -> str:
        return "stub-transform"

    def apply(self, item: DataItem) -> DataItem | None:
        return DataItem(
            content=item.content + self._suffix.encode(),
            label=item.label,
            media_type=item.media_type,
            source_name=item.source_name,
            extension=item.extension,
            metadata=item.metadata,
        )


class FilteringTransform:
    """Transform that discards all items."""

    @property
    def name(self) -> str:
        return "filter-all"

    def apply(self, item: DataItem) -> DataItem | None:
        return None


# ===================================================================
# 1. DataItem
# ===================================================================


class TestDataItem:
    def test_creation_with_defaults(self) -> None:
        item = DataItem(content=b"x", label=Label.REAL, media_type=MediaType.IMAGE, source_name="s")
        assert item.extension == ".jpg"
        assert item.metadata == {}

    def test_creation_with_all_fields(self) -> None:
        item = _make_item(extension=".png", metadata={"key": "val"})
        assert item.content == b"fake-image-bytes"
        assert item.label == Label.REAL
        assert item.media_type == MediaType.IMAGE
        assert item.source_name == "test-source"
        assert item.extension == ".png"
        assert item.metadata == {"key": "val"}

    def test_frozen(self) -> None:
        item = _make_item()
        with pytest.raises(dataclasses.FrozenInstanceError):
            item.content = b"changed"  # type: ignore[misc]

    def test_is_dataclass(self) -> None:
        assert dataclasses.is_dataclass(DataItem)

    def test_equality(self) -> None:
        a = _make_item()
        b = _make_item()
        assert a == b

    def test_metadata_default_not_shared(self) -> None:
        a = _make_item()
        b = _make_item()
        assert a.metadata is not b.metadata


# ===================================================================
# 2. Label enum
# ===================================================================


class TestLabel:
    def test_values(self) -> None:
        assert Label.REAL == 0
        assert Label.AI_GENERATED == 1

    def test_is_int(self) -> None:
        assert isinstance(Label.REAL, int)
        assert isinstance(Label.AI_GENERATED, int)

    def test_members(self) -> None:
        assert set(Label.__members__) == {"REAL", "AI_GENERATED"}


# ===================================================================
# 3. MediaType enum
# ===================================================================


class TestMediaType:
    def test_values(self) -> None:
        assert MediaType.IMAGE == "image"
        assert MediaType.TEXT == "text"
        assert MediaType.AUDIO == "audio"
        assert MediaType.VIDEO == "video"

    def test_is_str(self) -> None:
        assert isinstance(MediaType.IMAGE, str)

    def test_members(self) -> None:
        assert set(MediaType.__members__) == {"IMAGE", "TEXT", "AUDIO", "VIDEO"}


# ===================================================================
# 4. Source protocol
# ===================================================================


class TestSourceProtocol:
    def test_stub_is_source(self) -> None:
        assert isinstance(StubSource(), Source)

    def test_non_conforming_is_not_source(self) -> None:
        assert not isinstance(object(), Source)

    def test_local_source_is_source(self, tmp_path: Path) -> None:
        ls = LocalSource(directory=tmp_path, label=Label.REAL)
        assert isinstance(ls, Source)


# ===================================================================
# 5. Target protocol
# ===================================================================


class TestTargetProtocol:
    def test_stub_is_target(self) -> None:
        assert isinstance(StubTarget(), Target)

    def test_non_conforming_is_not_target(self) -> None:
        assert not isinstance(object(), Target)

    def test_local_target_is_target(self) -> None:
        assert isinstance(LocalTarget(), Target)


# ===================================================================
# 6. Transform protocol
# ===================================================================


class TestTransformProtocol:
    def test_stub_is_transform(self) -> None:
        assert isinstance(StubTransform(), Transform)

    def test_non_conforming_is_not_transform(self) -> None:
        assert not isinstance(object(), Transform)

    def test_filtering_transform_is_transform(self) -> None:
        assert isinstance(FilteringTransform(), Transform)


# ===================================================================
# 7. LocalSource
# ===================================================================


class TestLocalSource:
    def _populate(self, d: Path, ext: str = ".jpg", count: int = 3) -> list[Path]:
        files = []
        for i in range(count):
            p = d / f"img_{i:03d}{ext}"
            p.write_bytes(f"data-{i}".encode())
            files.append(p)
        return files

    @pytest.mark.asyncio
    async def test_fetch_real_files(self, tmp_path: Path) -> None:
        self._populate(tmp_path, count=3)
        source = LocalSource(directory=tmp_path, label=Label.REAL)
        items = [item async for item in source.fetch()]
        assert len(items) == 3
        for item in items:
            assert item.label == Label.REAL
            assert item.media_type == MediaType.IMAGE
            assert item.extension == ".jpg"
            assert item.source_name == f"local:{tmp_path.name}"
            assert "path" in item.metadata

    @pytest.mark.asyncio
    async def test_empty_directory(self, tmp_path: Path) -> None:
        source = LocalSource(directory=tmp_path, label=Label.AI_GENERATED)
        items = [item async for item in source.fetch()]
        assert items == []

    @pytest.mark.asyncio
    async def test_nonexistent_directory(self, tmp_path: Path) -> None:
        source = LocalSource(directory=tmp_path / "nope", label=Label.REAL)
        items = [item async for item in source.fetch()]
        assert items == []

    @pytest.mark.asyncio
    async def test_max_items(self, tmp_path: Path) -> None:
        self._populate(tmp_path, count=10)
        source = LocalSource(directory=tmp_path, label=Label.REAL, max_items=5)
        items = [item async for item in source.fetch()]
        assert len(items) == 5

    @pytest.mark.asyncio
    async def test_extension_filtering(self, tmp_path: Path) -> None:
        (tmp_path / "a.jpg").write_bytes(b"j")
        (tmp_path / "b.png").write_bytes(b"p")
        (tmp_path / "c.txt").write_bytes(b"t")
        (tmp_path / "d.csv").write_bytes(b"c")

        source = LocalSource(directory=tmp_path, label=Label.REAL)
        items = [item async for item in source.fetch()]
        extensions = {item.extension for item in items}
        assert extensions <= IMAGE_EXTENSIONS
        assert len(items) == 2  # .jpg and .png only

    @pytest.mark.asyncio
    async def test_custom_extensions(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_bytes(b"hello")
        (tmp_path / "b.md").write_bytes(b"world")
        source = LocalSource(
            directory=tmp_path, label=Label.REAL, media_type=MediaType.TEXT, extensions={".txt"}
        )
        items = [item async for item in source.fetch()]
        assert len(items) == 1
        assert items[0].extension == ".txt"
        assert items[0].media_type == MediaType.TEXT

    @pytest.mark.asyncio
    async def test_skips_subdirectories(self, tmp_path: Path) -> None:
        (tmp_path / "sub").mkdir()
        (tmp_path / "a.jpg").write_bytes(b"data")
        source = LocalSource(directory=tmp_path, label=Label.REAL)
        items = [item async for item in source.fetch()]
        assert len(items) == 1

    def test_name(self, tmp_path: Path) -> None:
        source = LocalSource(directory=tmp_path, label=Label.REAL)
        assert source.name == f"local:{tmp_path.name}"

    @pytest.mark.asyncio
    async def test_ai_generated_label(self, tmp_path: Path) -> None:
        (tmp_path / "a.jpg").write_bytes(b"data")
        source = LocalSource(directory=tmp_path, label=Label.AI_GENERATED)
        items = [item async for item in source.fetch()]
        assert items[0].label == Label.AI_GENERATED


# ===================================================================
# 8. LocalTarget
# ===================================================================


class TestLocalTarget:
    @pytest.mark.asyncio
    async def test_publish(self, tmp_path: Path) -> None:
        (tmp_path / "real").mkdir()
        (tmp_path / "ai").mkdir()
        (tmp_path / "real" / "a.jpg").write_bytes(b"r")
        (tmp_path / "ai" / "b.jpg").write_bytes(b"a")

        target = LocalTarget()
        result = await target.publish(tmp_path)
        assert result.target_name == "local"
        assert result.location == str(tmp_path)
        assert result.files_published == 2
        assert "saved" in result.message.lower() or str(tmp_path) in result.message

    @pytest.mark.asyncio
    async def test_publish_empty(self, tmp_path: Path) -> None:
        target = LocalTarget()
        result = await target.publish(tmp_path)
        assert result.files_published == 0

    def test_name(self) -> None:
        assert LocalTarget().name == "local"

    @pytest.mark.asyncio
    async def test_publish_with_metadata(self, tmp_path: Path) -> None:
        target = LocalTarget()
        result = await target.publish(tmp_path, metadata={"key": "value"})
        assert isinstance(result, PublishResult)


# ===================================================================
# 9. CollectorConfig
# ===================================================================


class TestCollectorConfig:
    def test_defaults(self) -> None:
        cfg = CollectorConfig()
        assert cfg.concurrency == 4
        assert cfg.source_timeout == 600.0
        assert cfg.force is False

    def test_custom_values(self, tmp_path: Path) -> None:
        cfg = CollectorConfig(output_dir=tmp_path, concurrency=2, source_timeout=30.0, force=True)
        assert cfg.output_dir == tmp_path
        assert cfg.concurrency == 2
        assert cfg.source_timeout == 30.0
        assert cfg.force is True


# ===================================================================
# 10. CollectorResult
# ===================================================================


class TestCollectorResult:
    def test_defaults(self) -> None:
        r = CollectorResult()
        assert r.total_items == 0
        assert r.real_count == 0
        assert r.ai_count == 0
        assert r.source_stats == {}
        assert r.cached_sources == []
        assert r.publish_results == []
        assert r.duration_seconds == 0.0

    def test_mutable(self) -> None:
        r = CollectorResult()
        r.total_items = 10
        r.real_count = 6
        r.ai_count = 4
        assert r.total_items == 10


# ===================================================================
# 11. PublishResult
# ===================================================================


class TestPublishResult:
    def test_creation(self) -> None:
        r = PublishResult(target_name="t", location="/here", files_published=5)
        assert r.target_name == "t"
        assert r.location == "/here"
        assert r.files_published == 5
        assert r.message == ""

    def test_frozen(self) -> None:
        r = PublishResult(target_name="t", location="/here", files_published=5)
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.target_name = "x"  # type: ignore[misc]


# ===================================================================
# 12. Collector — full pipeline
# ===================================================================


class TestCollector:
    @pytest.mark.asyncio
    async def test_full_pipeline_local(self, tmp_path: Path) -> None:
        """End-to-end: LocalSource → Collector → LocalTarget."""
        src_dir = tmp_path / "src_real"
        src_dir.mkdir()
        for i in range(5):
            (src_dir / f"img_{i}.jpg").write_bytes(f"real-{i}".encode())

        ai_dir = tmp_path / "src_ai"
        ai_dir.mkdir()
        for i in range(3):
            (ai_dir / f"img_{i}.jpg").write_bytes(f"ai-{i}".encode())

        out_dir = tmp_path / "output"

        sources = [
            LocalSource(directory=src_dir, label=Label.REAL),
            LocalSource(directory=ai_dir, label=Label.AI_GENERATED),
        ]
        target = LocalTarget()
        config = CollectorConfig(output_dir=out_dir)

        collector = Collector(sources=sources, targets=[target], config=config)
        result = await collector.run()

        assert result.total_items == 8
        assert result.real_count == 5
        assert result.ai_count == 3
        assert (out_dir / "real").is_dir()
        assert (out_dir / "ai").is_dir()
        assert len(list((out_dir / "real").glob("*.jpg"))) == 5
        assert len(list((out_dir / "ai").glob("*.jpg"))) == 3
        assert len(result.publish_results) == 1
        assert result.duration_seconds > 0

    @pytest.mark.asyncio
    async def test_empty_sources(self, tmp_path: Path) -> None:
        config = CollectorConfig(output_dir=tmp_path / "out")
        collector = Collector(sources=[], config=config)
        result = await collector.run()
        assert result.total_items == 0

    @pytest.mark.asyncio
    async def test_with_stub_source_and_target(self, tmp_path: Path) -> None:
        items = [
            _make_item(content=b"one", label=Label.REAL),
            _make_item(content=b"two", label=Label.AI_GENERATED),
        ]
        source = StubSource(items)
        target = StubTarget()
        config = CollectorConfig(output_dir=tmp_path / "out")

        collector = Collector(sources=[source], targets=[target], config=config)
        result = await collector.run()

        assert result.total_items == 2
        assert result.real_count == 1
        assert result.ai_count == 1
        assert len(target.published_dirs) == 1

    @pytest.mark.asyncio
    async def test_cancel(self, tmp_path: Path) -> None:
        """Cancelling should stop the collector mid-run."""

        class SlowSource:
            @property
            def name(self) -> str:
                return "slow"

            async def fetch(self) -> AsyncIterator[DataItem]:
                for i in range(1000):
                    yield _make_item(content=f"item-{i}".encode())
                    await asyncio.sleep(0)

        config = CollectorConfig(output_dir=tmp_path / "out")
        collector = Collector(sources=[SlowSource()], config=config)

        async def cancel_soon() -> None:
            await asyncio.sleep(0.01)
            collector.cancel()

        task = asyncio.create_task(cancel_soon())
        result = await collector.run()
        await task

        assert result.total_items < 1000

    @pytest.mark.asyncio
    async def test_transforms_applied(self, tmp_path: Path) -> None:
        items = [_make_item(content=b"raw")]
        source = StubSource(items)
        transform = StubTransform(suffix="-t")
        config = CollectorConfig(output_dir=tmp_path / "out")

        collector = Collector(sources=[source], transforms=[transform], config=config)
        result = await collector.run()

        assert result.total_items == 1
        saved = list((tmp_path / "out" / "real").glob("*"))
        assert len(saved) == 1
        assert saved[0].read_bytes() == b"raw-t"

    @pytest.mark.asyncio
    async def test_filtering_transform_discards_items(self, tmp_path: Path) -> None:
        items = [_make_item(), _make_item()]
        source = StubSource(items)
        config = CollectorConfig(output_dir=tmp_path / "out")

        collector = Collector(sources=[source], transforms=[FilteringTransform()], config=config)
        result = await collector.run()

        assert result.total_items == 0

    @pytest.mark.asyncio
    async def test_multiple_transforms_chained(self, tmp_path: Path) -> None:
        items = [_make_item(content=b"x")]
        source = StubSource(items)
        t1 = StubTransform(suffix="-a")
        t2 = StubTransform(suffix="-b")
        config = CollectorConfig(output_dir=tmp_path / "out")

        collector = Collector(sources=[source], transforms=[t1, t2], config=config)
        result = await collector.run()

        assert result.total_items == 1
        saved = list((tmp_path / "out" / "real").glob("*"))
        assert saved[0].read_bytes() == b"x-a-b"

    @pytest.mark.asyncio
    async def test_source_stats_populated(self, tmp_path: Path) -> None:
        items = [_make_item(label=Label.REAL), _make_item(label=Label.AI_GENERATED)]
        source = StubSource(items)
        config = CollectorConfig(output_dir=tmp_path / "out")

        collector = Collector(sources=[source], config=config)
        result = await collector.run()

        assert "stub-source" in result.source_stats
        stats = result.source_stats["stub-source"]
        assert stats["total"] == 2
        assert stats["real"] == 1
        assert stats["ai"] == 1

    @pytest.mark.asyncio
    async def test_no_targets(self, tmp_path: Path) -> None:
        items = [_make_item()]
        source = StubSource(items)
        config = CollectorConfig(output_dir=tmp_path / "out")

        collector = Collector(sources=[source], config=config)
        result = await collector.run()

        assert result.total_items == 1
        assert result.publish_results == []

    @pytest.mark.asyncio
    async def test_output_dir_created(self, tmp_path: Path) -> None:
        out = tmp_path / "nested" / "deep" / "out"
        config = CollectorConfig(output_dir=out)
        collector = Collector(sources=[StubSource([_make_item()])], config=config)
        await collector.run()
        assert out.is_dir()
        assert (out / "real").is_dir()
        assert (out / "ai").is_dir()


# ===================================================================
# 13. Manifest / caching helpers
# ===================================================================


class TestManifest:
    def test_load_manifest_empty(self, tmp_path: Path) -> None:
        assert _load_manifest(tmp_path) == {}

    def test_save_and_load(self, tmp_path: Path) -> None:
        data = {"sources": {"src1": {"status": "done"}}}
        _save_manifest(tmp_path, data)
        assert (tmp_path / MANIFEST_FILE).exists()
        loaded = _load_manifest(tmp_path)
        assert loaded == data

    def test_load_corrupt_manifest(self, tmp_path: Path) -> None:
        (tmp_path / MANIFEST_FILE).write_text("not json!!!")
        assert _load_manifest(tmp_path) == {}

    def test_source_cache_key_minimal(self) -> None:
        source = StubSource()
        key = _source_cache_key(source)
        assert key == {"name": "stub-source"}

    @pytest.mark.asyncio
    async def test_incremental_build_uses_cache(self, tmp_path: Path) -> None:
        """Second run should skip already-completed sources."""
        items = [_make_item()]
        source = StubSource(items)
        config = CollectorConfig(output_dir=tmp_path / "out")

        # First run
        c1 = Collector(sources=[source], config=config)
        r1 = await c1.run()
        assert r1.total_items == 1
        assert r1.cached_sources == []

        # Second run — source should be cached
        c2 = Collector(sources=[source], config=config)
        r2 = await c2.run()
        assert "stub-source" in r2.cached_sources
        # Items from cache are counted
        assert r2.total_items == 1

    @pytest.mark.asyncio
    async def test_force_ignores_cache(self, tmp_path: Path) -> None:
        items = [_make_item()]
        source = StubSource(items)
        out = tmp_path / "out"
        config = CollectorConfig(output_dir=out)

        c1 = Collector(sources=[source], config=config)
        await c1.run()

        config_force = CollectorConfig(output_dir=out, force=True)
        c2 = Collector(sources=[source], config=config_force)
        r2 = await c2.run()
        assert r2.cached_sources == []
        assert r2.total_items == 1


# ===================================================================
# 14. ResizeTransform
# ===================================================================


class TestResizeTransform:
    def test_name_property(self) -> None:
        t = ResizeTransform(width=128, height=128)
        assert t.name == "resize-128x128"

    def test_default_name(self) -> None:
        t = ResizeTransform()
        assert t.name == "resize-256x256"

    def test_is_transform(self) -> None:
        assert isinstance(ResizeTransform(), Transform)

    @pytest.mark.asyncio
    async def test_apply_with_pillow(self) -> None:
        """Test actual resize if Pillow is available."""
        pytest.importorskip("PIL")
        import io

        from PIL import Image

        img = Image.new("RGB", (512, 512), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        raw = buf.getvalue()

        item = _make_item(content=raw)
        t = ResizeTransform(width=64, height=64)
        result = t.apply(item)

        assert result is not None
        assert result.extension == ".jpg"
        resized = Image.open(io.BytesIO(result.content))
        assert resized.size == (64, 64)

    def test_apply_invalid_content_returns_none(self) -> None:
        """Non-image bytes should cause apply to return None."""
        pytest.importorskip("PIL")
        item = _make_item(content=b"not an image")
        t = ResizeTransform()
        result = t.apply(item)
        assert result is None


# ===================================================================
# 15. Collector timeout
# ===================================================================


class TestCollectorTimeout:
    @pytest.mark.asyncio
    async def test_source_timeout(self, tmp_path: Path) -> None:
        """Source exceeding timeout should be interrupted."""

        class InfiniteSource:
            @property
            def name(self) -> str:
                return "infinite"

            async def fetch(self) -> AsyncIterator[DataItem]:
                i = 0
                while True:
                    yield _make_item(content=f"item-{i}".encode())
                    i += 1
                    await asyncio.sleep(0)

        config = CollectorConfig(output_dir=tmp_path / "out", source_timeout=0.05)
        collector = Collector(sources=[InfiniteSource()], config=config)
        result = await collector.run()

        # Should have collected some items but not infinitely many
        assert result.total_items > 0
        assert result.total_items < 100_000
