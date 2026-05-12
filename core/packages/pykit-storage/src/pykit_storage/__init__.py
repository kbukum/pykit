"""pykit_storage — Async object-storage abstraction (local, S3)."""

from __future__ import annotations

from pykit_storage.base import FileInfo, SignedURLProvider, Storage
from pykit_storage.component import StorageComponent
from pykit_storage.config import StorageConfig
from pykit_storage.local import LocalStorage
from pykit_storage.registry import StorageRegistry, default_storage_registry, register_local

__all__ = [
    "FileInfo",
    "LocalStorage",
    "SignedURLProvider",
    "Storage",
    "StorageComponent",
    "StorageConfig",
    "StorageRegistry",
    "default_storage_registry",
    "register_local",
]
