"""Core storage abstractions: Storage protocol and FileInfo."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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

    async def upload(self, path: str, data: bytes | BinaryIO) -> None: ...

    async def download(self, path: str) -> bytes: ...

    async def delete(self, path: str) -> None: ...

    async def exists(self, path: str) -> bool: ...

    async def list(self, prefix: str = "") -> list[FileInfo]: ...

    async def url(self, path: str) -> str: ...
