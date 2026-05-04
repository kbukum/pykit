"""Extended tests for pykit-storage — path traversal, concurrency, edge cases."""

from __future__ import annotations

import asyncio
import os
from io import BytesIO
from pathlib import Path

import pytest

from pykit_errors import InvalidInputError, NotFoundError
from pykit_storage import FileInfo, LocalStorage, StorageConfig
from pykit_storage.s3 import S3Storage, validate_key

# ---------------------------------------------------------------------------
# Path traversal security
# ---------------------------------------------------------------------------


class TestPathTraversalSecurity:
    @pytest.fixture
    def store(self, tmp_path: Path) -> LocalStorage:
        return LocalStorage(base_path=str(tmp_path))

    async def test_upload_traversal_rejected(self, store: LocalStorage, tmp_path: Path) -> None:
        """Upload with ../../ must not escape the storage base."""
        with pytest.raises(InvalidInputError):
            await store.upload("../../etc/passwd", b"hacked")
        assert list(tmp_path.rglob("*")) == []

    async def test_download_traversal_returns_error_or_not_found(
        self, store: LocalStorage, tmp_path: Path
    ) -> None:
        """Downloading a traversal path should fail cleanly."""
        with pytest.raises((InvalidInputError, NotFoundError, FileNotFoundError, OSError)):
            await store.download("../../../etc/shadow")

    async def test_exists_traversal_path(self, store: LocalStorage) -> None:
        """Exists with traversal path should not crash."""
        with pytest.raises(InvalidInputError):
            await store.exists("../../etc/passwd")

    async def test_delete_traversal_nonexistent_is_noop(self, store: LocalStorage) -> None:
        """Delete with traversal on nonexistent path should not crash."""
        with pytest.raises(InvalidInputError):
            await store.delete("../../nonexistent_file.txt")


class TestS3ConfigValidation:
    def test_s3_key_rejects_path_traversal(self) -> None:
        with pytest.raises(InvalidInputError, match="normalized relative"):
            validate_key("../secret")

    def test_s3_key_rejects_absolute_paths(self) -> None:
        with pytest.raises(InvalidInputError, match="normalized relative"):
            validate_key("/bucket/key")

    def test_s3_key_accepts_normalized_relative_key(self) -> None:
        assert validate_key("tenant/a.txt") == "tenant/a.txt"

    async def test_s3_stream_upload_uses_file_object_api(self) -> None:
        storage = S3Storage.__new__(S3Storage)
        storage._bucket = "bucket"
        storage._client = _FakeS3ClientContext  # type: ignore[method-assign]
        stream = _UnreadableStream(b"payload")

        await storage.upload("tenant/a.bin", stream)

        assert _FakeS3Client.last_uploaded is stream
        assert _FakeS3Client.last_bucket == "bucket"
        assert _FakeS3Client.last_key == "tenant/a.bin"

    async def test_s3_exists_handles_botocore_client_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("pykit_storage.s3._client_error_type", lambda: _FakeClientError)
        storage = S3Storage.__new__(S3Storage)
        storage._bucket = "bucket"
        storage._client = _MissingS3ClientContext  # type: ignore[method-assign]

        assert await storage.exists("tenant/missing.bin") is False

    async def test_s3_download_maps_botocore_client_error_to_not_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("pykit_storage.s3._client_error_type", lambda: _FakeClientError)
        storage = S3Storage.__new__(S3Storage)
        storage._bucket = "bucket"
        storage._client = _MissingS3ClientContext  # type: ignore[method-assign]

        with pytest.raises(NotFoundError):
            await storage.download("tenant/missing.bin")


class _UnreadableStream(BytesIO):
    def read(self, *_args: object, **_kwargs: object) -> bytes:
        raise AssertionError("stream upload must not read the entire body into memory")


class _FakeS3Client:
    last_uploaded: object = None
    last_bucket = ""
    last_key = ""

    async def upload_fileobj(self, data: object, bucket: str, key: str) -> None:
        self.__class__.last_uploaded = data
        self.__class__.last_bucket = bucket
        self.__class__.last_key = key


class _FakeS3ClientContext:
    async def __aenter__(self) -> _FakeS3Client:
        return _FakeS3Client()

    async def __aexit__(self, *_exc: object) -> None:
        return None


class _FakeClientError(Exception):
    def __init__(self) -> None:
        super().__init__("missing")
        self.response = {"Error": {"Code": "404"}}


class _ModeledExceptions:
    class NoSuchKey(Exception):
        pass


class _MissingS3Client:
    exceptions = _ModeledExceptions

    async def head_object(self, **_kwargs: object) -> None:
        raise _FakeClientError()

    async def get_object(self, **_kwargs: object) -> object:
        raise _FakeClientError()


class _MissingS3ClientContext:
    async def __aenter__(self) -> _MissingS3Client:
        return _MissingS3Client()

    async def __aexit__(self, *_exc: object) -> None:
        return None


# ---------------------------------------------------------------------------
# Concurrent operations
# ---------------------------------------------------------------------------


class TestConcurrentOperations:
    @pytest.fixture
    def store(self, tmp_path: Path) -> LocalStorage:
        return LocalStorage(base_path=str(tmp_path))

    async def test_concurrent_uploads(self, store: LocalStorage) -> None:
        """Multiple concurrent uploads should not corrupt each other."""
        n = 20
        tasks = [store.upload(f"concurrent/{i}.txt", f"content-{i}".encode()) for i in range(n)]
        await asyncio.gather(*tasks)

        for i in range(n):
            data = await store.download(f"concurrent/{i}.txt")
            assert data == f"content-{i}".encode()

    async def test_concurrent_reads(self, store: LocalStorage) -> None:
        """Multiple concurrent reads of the same file should all succeed."""
        await store.upload("shared.txt", b"shared content")

        tasks = [store.download("shared.txt") for _ in range(20)]
        results = await asyncio.gather(*tasks)

        for data in results:
            assert data == b"shared content"

    async def test_concurrent_upload_and_delete(self, store: LocalStorage) -> None:
        """Upload and delete in parallel should not deadlock."""
        await store.upload("ephemeral.txt", b"temp data")

        async def upload_then_check(i: int) -> None:
            key = f"para/{i}.txt"
            await store.upload(key, f"data-{i}".encode())
            assert await store.exists(key)

        tasks = [upload_then_check(i) for i in range(10)]
        await asyncio.gather(*tasks)

    async def test_concurrent_list_during_writes(self, store: LocalStorage) -> None:
        """Listing while uploads are happening should not crash."""
        for i in range(5):
            await store.upload(f"listing/{i}.txt", b"x")

        async def upload_more() -> None:
            for i in range(5, 10):
                await store.upload(f"listing/{i}.txt", b"y")

        async def list_repeatedly() -> None:
            for _ in range(5):
                await store.list("listing")

        await asyncio.gather(upload_more(), list_repeatedly())


# ---------------------------------------------------------------------------
# Error scenarios
# ---------------------------------------------------------------------------


class TestErrorScenarios:
    @pytest.fixture
    def store(self, tmp_path: Path) -> LocalStorage:
        return LocalStorage(base_path=str(tmp_path))

    async def test_download_nonexistent_raises_not_found(self, store: LocalStorage) -> None:
        from pykit_errors import NotFoundError

        with pytest.raises(NotFoundError):
            await store.download("does_not_exist.bin")

    async def test_download_empty_path(self, store: LocalStorage) -> None:
        """Empty path download should fail cleanly."""
        from pykit_errors import InvalidInputError, NotFoundError

        with pytest.raises((InvalidInputError, NotFoundError, IsADirectoryError, OSError)):
            await store.download("")

    async def test_list_nonexistent_prefix_returns_empty(self, store: LocalStorage) -> None:
        result = await store.list("no_such_prefix")
        assert result == []

    async def test_exists_nonexistent_returns_false(self, store: LocalStorage) -> None:
        assert await store.exists("nope.txt") is False

    async def test_delete_nonexistent_no_error(self, store: LocalStorage) -> None:
        await store.delete("ghost.txt")  # should not raise


# ---------------------------------------------------------------------------
# Content-type detection
# ---------------------------------------------------------------------------


class TestContentTypeDetection:
    @pytest.fixture
    def store(self, tmp_path: Path) -> LocalStorage:
        return LocalStorage(base_path=str(tmp_path))

    async def test_list_returns_octet_stream_content_type(self, store: LocalStorage) -> None:
        """LocalStorage always returns application/octet-stream for content_type."""
        await store.upload("test.html", b"<html></html>")
        await store.upload("test.json", b'{"key": "value"}')
        items = await store.list()
        for item in items:
            assert item.content_type == "application/octet-stream"

    async def test_file_info_has_all_fields(self, store: LocalStorage) -> None:
        await store.upload("info.txt", b"hello")
        items = await store.list()
        assert len(items) == 1
        info = items[0]
        assert isinstance(info, FileInfo)
        assert info.path == "info.txt"
        assert info.size == 5
        assert info.last_modified is not None
        assert info.content_type == "application/octet-stream"


# ---------------------------------------------------------------------------
# Large file handling
# ---------------------------------------------------------------------------


class TestLargeFileHandling:
    @pytest.fixture
    def store(self, tmp_path: Path) -> LocalStorage:
        return LocalStorage(base_path=str(tmp_path))

    async def test_large_file_roundtrip(self, store: LocalStorage) -> None:
        """2MB file should upload and download correctly."""
        size = 2 * 1024 * 1024
        data = bytes(i % 251 for i in range(size))
        await store.upload("large.bin", data)
        result = await store.download("large.bin")
        assert len(result) == size
        assert result == data

    async def test_large_file_exists_and_list(self, store: LocalStorage) -> None:
        """Large file should appear in exists and list."""
        size = 1024 * 1024
        data = b"\x00" * size
        await store.upload("big.dat", data)
        assert await store.exists("big.dat") is True
        items = await store.list()
        assert len(items) == 1
        assert items[0].size == size


# ---------------------------------------------------------------------------
# Directory creation edge cases
# ---------------------------------------------------------------------------


class TestDirectoryEdgeCases:
    @pytest.fixture
    def store(self, tmp_path: Path) -> LocalStorage:
        return LocalStorage(base_path=str(tmp_path))

    async def test_deeply_nested_upload(self, store: LocalStorage) -> None:
        """Uploading to a deeply nested path should auto-create dirs."""
        deep_path = "a/b/c/d/e/f/g/h/deep.txt"
        await store.upload(deep_path, b"deep content")
        data = await store.download(deep_path)
        assert data == b"deep content"

    async def test_upload_with_special_characters_in_name(self, store: LocalStorage) -> None:
        """File names with spaces and special chars should work."""
        await store.upload("my file (1).txt", b"special")
        data = await store.download("my file (1).txt")
        assert data == b"special"

    async def test_upload_overwrite(self, store: LocalStorage) -> None:
        """Uploading to the same path should overwrite."""
        await store.upload("overwrite.txt", b"v1")
        await store.upload("overwrite.txt", b"v2")
        data = await store.download("overwrite.txt")
        assert data == b"v2"

    async def test_upload_empty_file(self, store: LocalStorage) -> None:
        await store.upload("empty.bin", b"")
        data = await store.download("empty.bin")
        assert data == b""

    async def test_upload_binary_content(self, store: LocalStorage) -> None:
        data = bytes(range(256))
        await store.upload("binary.dat", data)
        result = await store.download("binary.dat")
        assert result == data


# ---------------------------------------------------------------------------
# Filter patterns in listing
# ---------------------------------------------------------------------------


class TestListingFilters:
    @pytest.fixture
    def store(self, tmp_path: Path) -> LocalStorage:
        return LocalStorage(base_path=str(tmp_path))

    async def test_list_with_nested_prefix(self, store: LocalStorage) -> None:
        await store.upload("imgs/photos/a.jpg", b"a")
        await store.upload("imgs/photos/b.jpg", b"b")
        await store.upload("imgs/icons/c.png", b"c")
        await store.upload("docs/readme.md", b"d")

        items = await store.list("imgs")
        assert len(items) == 3

        items = await store.list("imgs/photos")
        assert len(items) == 2

    async def test_list_root_returns_all(self, store: LocalStorage) -> None:
        await store.upload("a.txt", b"a")
        await store.upload("sub/b.txt", b"b")
        items = await store.list()
        assert len(items) == 2

    async def test_list_preserves_relative_paths(self, store: LocalStorage) -> None:
        await store.upload("dir/file.txt", b"x")
        items = await store.list("dir")
        assert len(items) == 1
        assert items[0].path == "dir/file.txt"

    async def test_list_file_info_size_accuracy(self, store: LocalStorage) -> None:
        data = b"exactly twenty bytes"
        await store.upload("sized.txt", data)
        items = await store.list()
        assert items[0].size == len(data)


# ---------------------------------------------------------------------------
# URL generation
# ---------------------------------------------------------------------------


class TestURLGeneration:
    async def test_url_with_public_url_strips_trailing_slash(self, tmp_path: Path) -> None:
        store = LocalStorage(base_path=str(tmp_path), public_url="https://cdn.example.com/")
        result = await store.url("path/to/file.txt")
        assert result == "https://cdn.example.com/path/to/file.txt"

    async def test_url_with_public_url_rejects_traversal(self, tmp_path: Path) -> None:
        store = LocalStorage(base_path=str(tmp_path), public_url="https://cdn.example.com/")
        with pytest.raises(InvalidInputError, match="normalized relative"):
            await store.url("../secret.txt")

    async def test_url_without_public_url_returns_local_path(self, tmp_path: Path) -> None:
        store = LocalStorage(base_path=str(tmp_path))
        result = await store.url("file.txt")
        assert result == os.path.join(str(tmp_path), "file.txt")


# ---------------------------------------------------------------------------
# Config edge cases
# ---------------------------------------------------------------------------


class TestStorageConfigExtended:
    def test_custom_config_values(self) -> None:
        cfg = StorageConfig(
            name="custom",
            provider="s3",
            enabled=False,
            base_path="/custom/path",
            max_file_size=50_000_000,
            public_url="https://cdn.test.com",
            allowed_types=["image/png", "image/jpeg"],
        )
        assert cfg.name == "custom"
        assert cfg.provider == "s3"
        assert cfg.enabled is False
        assert cfg.base_path == "/custom/path"
        assert cfg.max_file_size == 50_000_000
        assert cfg.public_url == "https://cdn.test.com"
        assert cfg.allowed_types == ["image/png", "image/jpeg"]

    def test_default_max_file_size_is_100mb(self) -> None:
        cfg = StorageConfig()
        assert cfg.max_file_size == 100 * 1024 * 1024

    def test_default_allowed_types_is_empty(self) -> None:
        cfg = StorageConfig()
        assert cfg.allowed_types == []

    def test_allowed_types_not_shared_between_instances(self) -> None:
        """Mutable default list should not be shared."""
        cfg1 = StorageConfig()
        cfg2 = StorageConfig()
        cfg1.allowed_types.append("image/png")
        assert "image/png" not in cfg2.allowed_types
