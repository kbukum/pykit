"""Core storage abstractions: Storage protocol and FileInfo."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import BinaryIO, Protocol, runtime_checkable


@dataclass(frozen=True)
class FileInfo:
    """Metadata about a stored file."""

    path: str
    size: int
    last_modified: datetime
    content_type: str


@runtime_checkable
class Storage(Protocol):
    """Async object-storage interface (local, S3, etc.)."""

    async def upload(self, path: str, data: bytes | BinaryIO) -> None:
        """Upload data to the given storage path."""

    async def download(self, path: str) -> bytes:
        """Download the file contents for the given path."""

    async def delete(self, path: str) -> None:
        """Delete the object stored at the given path."""

    async def exists(self, path: str) -> bool:
        """Return whether an object exists at the given path."""

    async def list(self, prefix: str = "") -> list[FileInfo]:
        """List stored files under the given prefix."""

    async def url(self, path: str) -> str:
        """Return a URL for accessing the given path."""


@runtime_checkable
class SignedURLProvider(Protocol):
    """Optionally implemented by storage backends that support presigned URLs."""

    async def signed_url(self, path: str, expiry: timedelta) -> str:
        """Return a time-limited URL for the given path."""
