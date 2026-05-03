"""Local filesystem storage backend."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO, cast

import aiofiles
import aiofiles.os

from pykit_errors import InvalidInputError
from pykit_storage.base import FileInfo


class LocalStorage:
    """Storage implementation backed by the local filesystem."""

    def __init__(self, base_path: str, public_url: str = "") -> None:
        self._base_path = str(Path(base_path).resolve())
        self._public_url = public_url.rstrip("/")

    def _resolve(self, path: str, *, allow_empty: bool = False) -> str:
        if allow_empty and path == "":
            return self._base_path
        if path == "" or "\x00" in path:
            raise InvalidInputError(
                "storage path must be non-empty and must not contain NUL bytes", field="path"
            )
        if Path(path).is_absolute():
            raise InvalidInputError("storage path must be relative", field="path")
        if any(part in {".", ".."} for part in Path(path).parts):
            raise InvalidInputError("storage path must be a normalized relative path", field="path")
        resolved = (Path(self._base_path) / path).resolve()
        base = Path(self._base_path)
        if resolved != base and base not in resolved.parents:
            raise InvalidInputError("storage path escapes base path", field="path")
        return str(resolved)

    async def upload(self, path: str, data: bytes | BinaryIO) -> None:
        full = self._resolve(path)
        await aiofiles.os.makedirs(os.path.dirname(full), exist_ok=True)
        raw = data if isinstance(data, bytes) else await asyncio.to_thread(data.read)
        async with aiofiles.open(full, "wb") as f:
            await f.write(raw)

    async def download(self, path: str) -> bytes:
        full = self._resolve(path)
        if not await aiofiles.os.path.exists(full):
            from pykit_errors import NotFoundError

            raise NotFoundError("file", path)
        async with aiofiles.open(full, "rb") as f:
            return cast("bytes", await f.read())

    async def delete(self, path: str) -> None:
        full = self._resolve(path)
        if await aiofiles.os.path.exists(full):
            await aiofiles.os.remove(full)

    async def exists(self, path: str) -> bool:
        return bool(await aiofiles.os.path.exists(self._resolve(path)))

    async def list(self, prefix: str = "") -> list[FileInfo]:
        root = self._resolve(prefix, allow_empty=True)
        if not await aiofiles.os.path.isdir(root):
            return []

        def _list_sync() -> list[FileInfo]:
            results: list[FileInfo] = []
            for dirpath, _, filenames in os.walk(root):
                for name in sorted(filenames):
                    full = os.path.join(dirpath, name)
                    stat = os.stat(full)
                    rel = os.path.relpath(full, self._base_path)
                    results.append(
                        FileInfo(
                            path=rel,
                            size=stat.st_size,
                            last_modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                            content_type="application/octet-stream",
                        )
                    )
            return results

        return await asyncio.to_thread(_list_sync)

    async def url(self, path: str) -> str:
        if self._public_url:
            return f"{self._public_url}/{path}"
        return self._resolve(path)
