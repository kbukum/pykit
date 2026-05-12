"""S3 adapter for pykit-storage."""

from __future__ import annotations

from pykit_storage_s3.provider import S3Storage, register, validate_key

__all__ = ["S3Storage", "register", "validate_key"]
