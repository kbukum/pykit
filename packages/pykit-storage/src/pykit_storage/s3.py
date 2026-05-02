"""Optional S3 storage adapter."""

from __future__ import annotations

import asyncio
import importlib
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, BinaryIO

from pykit_errors import AppError, InvalidInputError, NotFoundError
from pykit_errors.codes import ErrorCode
from pykit_storage.base import FileInfo
from pykit_storage.config import StorageConfig

if TYPE_CHECKING:
    from pykit_storage.registry import StorageRegistry


class S3Storage:
    """S3 object storage backend requiring explicit registration."""

    def __init__(self, config: StorageConfig) -> None:
        if not config.bucket:
            raise InvalidInputError("S3 bucket is required", field="bucket")
        try:
            aioboto3 = importlib.import_module("aioboto3")
        except ImportError as exc:
            msg = "aioboto3 is required for S3Storage; install pykit-storage[s3]"
            raise ImportError(msg) from exc

        kwargs: dict[str, str] = {}
        if config.region:
            kwargs["region_name"] = config.region
        if config.access_key_id:
            kwargs["aws_access_key_id"] = config.access_key_id
        if config.secret_access_key:
            kwargs["aws_secret_access_key"] = config.secret_access_key
        self._session = aioboto3.Session(**kwargs)
        self._bucket = config.bucket
        self._endpoint_url = config.endpoint_url
        self._signed_url_max_seconds = config.signed_url_max_seconds

    async def upload(self, path: str, data: bytes | BinaryIO) -> None:
        """Upload bytes or a binary stream to S3."""
        key = _validate_key(path)
        raw = data if isinstance(data, bytes) else await asyncio.to_thread(data.read)
        async with self._client() as client:
            await client.put_object(Bucket=self._bucket, Key=key, Body=raw)

    async def download(self, path: str) -> bytes:
        """Download an object from S3."""
        key = _validate_key(path)
        async with self._client() as client:
            try:
                response = await client.get_object(Bucket=self._bucket, Key=key)
            except client.exceptions.NoSuchKey as exc:
                raise NotFoundError("file", key) from exc
            body = response["Body"]
            return bytes(await body.read())

    async def delete(self, path: str) -> None:
        """Delete an object from S3."""
        key = _validate_key(path)
        async with self._client() as client:
            await client.delete_object(Bucket=self._bucket, Key=key)

    async def exists(self, path: str) -> bool:
        """Return whether an object exists."""
        key = _validate_key(path)
        async with self._client() as client:
            try:
                await client.head_object(Bucket=self._bucket, Key=key)
            except client.exceptions.NoSuchKey:
                return False
            except client.exceptions.ClientError as exc:
                error = exc.response.get("Error", {})
                if error.get("Code") in {"404", "NoSuchKey", "NotFound"}:
                    return False
                raise AppError(ErrorCode.EXTERNAL_SERVICE, "S3 head_object failed").with_cause(exc) from exc
            return True

    async def list(self, prefix: str = "") -> list[FileInfo]:
        """List object metadata under a prefix."""
        safe_prefix = "" if prefix == "" else _validate_key(prefix.rstrip("/") + "/")
        items: list[FileInfo] = []
        async with self._client() as client:
            paginator = client.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=self._bucket, Prefix=safe_prefix):
                for obj in page.get("Contents", []):
                    modified = obj.get("LastModified")
                    items.append(
                        FileInfo(
                            path=str(obj["Key"]),
                            size=int(obj.get("Size", 0)),
                            last_modified=modified
                            if isinstance(modified, datetime)
                            else datetime.now(tz=UTC),
                            content_type="application/octet-stream",
                        )
                    )
        return items

    async def url(self, path: str) -> str:
        """Return an s3:// URL for the object."""
        return f"s3://{self._bucket}/{_validate_key(path)}"

    async def signed_url(self, path: str, expiry: timedelta) -> str:
        """Create a bounded presigned GET URL."""
        seconds = int(expiry.total_seconds())
        if seconds <= 0 or seconds > self._signed_url_max_seconds:
            raise InvalidInputError("signed URL expiry is out of bounds", field="expiry")
        async with self._client() as client:
            return str(
                await client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self._bucket, "Key": _validate_key(path)},
                    ExpiresIn=seconds,
                )
            )

    def _client(self) -> Any:
        return self._session.client("s3", endpoint_url=self._endpoint_url)


def _validate_key(path: str) -> str:
    if path == "" or "\x00" in path:
        raise InvalidInputError("storage key must be non-empty and must not contain NUL bytes", field="path")
    if path.startswith("/") or any(part in {"", ".", ".."} for part in path.split("/")):
        raise InvalidInputError("storage key must be a normalized relative path", field="path")
    return path


def register(registry: StorageRegistry) -> None:
    """Register the S3 backend in an injected registry."""
    registry.register("s3", S3Storage)
