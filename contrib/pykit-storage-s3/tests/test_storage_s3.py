"""S3 adapter tests."""

from __future__ import annotations

from io import BytesIO

import pytest

from pykit_errors import InvalidInputError, NotFoundError
from pykit_storage_s3 import S3Storage, validate_key


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
        monkeypatch.setattr("pykit_storage_s3.provider._client_error_type", lambda: _FakeClientError)
        storage = S3Storage.__new__(S3Storage)
        storage._bucket = "bucket"
        storage._client = _MissingS3ClientContext  # type: ignore[method-assign]

        assert await storage.exists("tenant/missing.bin") is False

    async def test_s3_download_maps_botocore_client_error_to_not_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("pykit_storage_s3.provider._client_error_type", lambda: _FakeClientError)
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
