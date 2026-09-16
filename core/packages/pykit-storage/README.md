# pykit-storage

Store and retrieve objects through an async registry-backed API with a local default and optional S3 adapter.

## Installation

```bash
pip install pykit-storage
pip install pykit-storage-s3  # optional S3 adapter

uv add pykit-storage
uv add pykit-storage-s3  # optional S3 adapter
```

## Quick start

```python
from pykit_storage import StorageComponent, StorageConfig

component = StorageComponent(StorageConfig(provider="local", base_path="./uploads"))
await component.start()

storage = component.storage
await storage.upload("images/photo.jpg", image_bytes)
data = await storage.download("images/photo.jpg")
files = await storage.list("images")
```

Local paths are normalized relative paths. Absolute paths, traversal (`..`), empty paths, and NUL bytes are rejected before filesystem access.

## Registering the S3 adapter

```python
from pykit_storage import StorageComponent, StorageConfig, StorageRegistry, register_local
from pykit_storage_s3 import register as register_s3

registry = StorageRegistry()
register_local(registry)
register_s3(registry)

component = StorageComponent(
    StorageConfig(provider="s3", bucket="app-objects", region="us-east-1"),
    registry=registry,
)
await component.start()
```

The optional S3 adapter uses `aioboto3`, validates object keys, supports upload, download, delete, list, `s3://` URLs, and bounded presigned GET URLs.

## Core APIs

- **`Storage`** defines the async storage contract: `upload`, `download`, `delete`, `exists`, `list`, and `url`.
- **`StorageRegistry`** is an injected backend registry. Empty registries have no backends.
- **`StorageComponent`** adds lifecycle management and health checks.
- **`LocalStorage`** is the lean filesystem-backed default.
- **`SignedURLProvider`** and **`FileInfo`** cover signed URLs and file listing metadata.

## See also

- [Main pykit README](../../../README.md)
- [tests/](tests/)
