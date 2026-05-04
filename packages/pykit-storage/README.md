# pykit-storage

Async object-storage abstraction with local filesystem lean default and an optional S3 adapter.
Backends are selected from an injected registry; importing core has no adapter side effects.

## Installation

```bash
pip install pykit-storage
pip install 'pykit-storage[s3]'  # optional S3 adapter

uv add pykit-storage
uv add 'pykit-storage[s3]'  # optional S3 adapter
```

## Local Quick Start

```python
from pykit_storage import StorageComponent, StorageConfig

component = StorageComponent(StorageConfig(provider="local", base_path="./uploads"))
await component.start()

storage = component.storage
await storage.upload("images/photo.jpg", image_bytes)
data = await storage.download("images/photo.jpg")
files = await storage.list("images")
```

Local paths are normalized relative paths; absolute paths, traversal (`..`), empty paths, and NUL
bytes are rejected before filesystem access.

## Explicit S3 registration

```python
from pykit_storage import StorageComponent, StorageConfig, StorageRegistry, register_local
from pykit_storage.s3 import register as register_s3

registry = StorageRegistry()
register_local(registry)
register_s3(registry)

component = StorageComponent(
    StorageConfig(provider="s3", bucket="app-objects", region="us-east-1"),
    registry=registry,
)
await component.start()
```

The S3 adapter uses `aioboto3`, validates object keys, supports upload/download/delete/list,
`s3://` URLs, and bounded presigned GET URLs.

## Key Components

- **Storage** — async protocol: `upload`, `download`, `delete`, `exists`, `list`, `url`.
- **StorageRegistry** — injected backend registry; empty registries have no backends.
- **LocalStorage** — local filesystem default using `aiofiles`.
- **S3Storage** — optional adapter in `pykit_storage.s3`, registered explicitly.
