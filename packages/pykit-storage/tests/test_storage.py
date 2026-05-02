"""Tests for pykit-storage."""

from __future__ import annotations

from pathlib import Path

import pytest

from pykit_component import HealthStatus
from pykit_errors import NotFoundError
from pykit_storage import (
    FileInfo,
    LocalStorage,
    Storage,
    StorageComponent,
    StorageConfig,
    StorageRegistry,
    default_storage_registry,
    register_local,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestStorageConfig:
    def test_defaults(self) -> None:
        cfg = StorageConfig()
        assert cfg.name == "storage"
        assert cfg.provider == "local"
        assert cfg.enabled is True
        assert cfg.base_path == "./storage"
        assert cfg.max_file_size == 104_857_600
        assert cfg.public_url == ""
        assert cfg.allowed_types == []
        assert cfg.bucket == ""

    def test_empty_registry_has_no_side_effect_backends(self) -> None:
        registry = StorageRegistry()
        assert registry.names() == ()

    def test_explicit_local_registration(self, tmp_path: Path) -> None:
        registry = StorageRegistry()
        register_local(registry)
        storage = registry.create(StorageConfig(base_path=str(tmp_path)))
        assert isinstance(storage, LocalStorage)

    def test_default_registry_only_contains_local(self) -> None:
        assert default_storage_registry().names() == ("local",)


# ---------------------------------------------------------------------------
# LocalStorage
# ---------------------------------------------------------------------------


class TestLocalStorage:
    @pytest.fixture
    def store(self, tmp_path: Path) -> LocalStorage:
        return LocalStorage(base_path=str(tmp_path))

    async def test_upload_download_roundtrip(self, store: LocalStorage) -> None:
        await store.upload("docs/hello.txt", b"hello world")
        data = await store.download("docs/hello.txt")
        assert data == b"hello world"

    async def test_exists(self, store: LocalStorage) -> None:
        assert await store.exists("nope.txt") is False
        await store.upload("nope.txt", b"data")
        assert await store.exists("nope.txt") is True

    async def test_delete(self, store: LocalStorage) -> None:
        await store.upload("rm.txt", b"bye")
        assert await store.exists("rm.txt") is True
        await store.delete("rm.txt")
        assert await store.exists("rm.txt") is False

    async def test_delete_nonexistent_is_noop(self, store: LocalStorage) -> None:
        await store.delete("ghost.txt")  # should not raise

    async def test_list(self, store: LocalStorage) -> None:
        await store.upload("a.txt", b"aaa")
        await store.upload("sub/b.txt", b"bbb")
        items = await store.list()
        paths = sorted(i.path for i in items)
        assert paths == ["a.txt", "sub/b.txt"]
        assert all(isinstance(i, FileInfo) for i in items)

    async def test_list_with_prefix(self, store: LocalStorage) -> None:
        await store.upload("imgs/a.png", b"a")
        await store.upload("imgs/b.png", b"b")
        await store.upload("docs/c.txt", b"c")
        items = await store.list("imgs")
        assert len(items) == 2

    async def test_list_empty(self, store: LocalStorage) -> None:
        items = await store.list("nonexistent")
        assert items == []

    async def test_url_with_public_url(self, tmp_path: Path) -> None:
        store = LocalStorage(base_path=str(tmp_path), public_url="https://cdn.example.com")
        result = await store.url("imgs/photo.jpg")
        assert result == "https://cdn.example.com/imgs/photo.jpg"

    async def test_url_without_public_url(self, store: LocalStorage, tmp_path: Path) -> None:
        result = await store.url("imgs/photo.jpg")
        assert result == str(tmp_path / "imgs" / "photo.jpg")

    async def test_download_nonexistent_raises(self, store: LocalStorage) -> None:
        with pytest.raises(NotFoundError, match="file"):
            await store.download("missing.bin")

    async def test_satisfies_protocol(self, store: LocalStorage) -> None:
        assert isinstance(store, Storage)


# ---------------------------------------------------------------------------
# Component lifecycle
# ---------------------------------------------------------------------------


class TestStorageComponent:
    async def test_start_creates_local_storage(self, tmp_path: Path) -> None:
        cfg = StorageConfig(base_path=str(tmp_path))
        comp = StorageComponent(cfg)
        assert comp.storage is None

        await comp.start()
        assert comp.storage is not None
        assert isinstance(comp.storage, LocalStorage)

    async def test_stop_clears_storage(self, tmp_path: Path) -> None:
        cfg = StorageConfig(base_path=str(tmp_path))
        comp = StorageComponent(cfg)
        await comp.start()
        await comp.stop()
        assert comp.storage is None

    async def test_health_healthy(self, tmp_path: Path) -> None:
        cfg = StorageConfig(base_path=str(tmp_path))
        comp = StorageComponent(cfg)
        await comp.start()
        h = await comp.health()
        assert h.status == HealthStatus.HEALTHY

    async def test_health_unhealthy_before_start(self) -> None:
        comp = StorageComponent()
        h = await comp.health()
        assert h.status == HealthStatus.UNHEALTHY

    async def test_name(self) -> None:
        comp = StorageComponent(StorageConfig(name="my-storage"))
        assert comp.name == "my-storage"

    async def test_unknown_provider_raises(self) -> None:
        comp = StorageComponent(StorageConfig(provider="gcs"))
        with pytest.raises(Exception, match="not registered"):
            await comp.start()

    async def test_s3_provider_requires_explicit_registration(self) -> None:
        comp = StorageComponent(StorageConfig(provider="s3"))
        with pytest.raises(Exception, match="not registered"):
            await comp.start()

    async def test_roundtrip_through_component(self, tmp_path: Path) -> None:
        cfg = StorageConfig(base_path=str(tmp_path))
        comp = StorageComponent(cfg)
        await comp.start()
        assert comp.storage is not None
        await comp.storage.upload("test.bin", b"\x00\x01\x02")
        data = await comp.storage.download("test.bin")
        assert data == b"\x00\x01\x02"
        await comp.stop()
