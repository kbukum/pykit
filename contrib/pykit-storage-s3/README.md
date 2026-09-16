# pykit-storage-s3

S3 backend for `pykit-storage`.

## Installation

```bash
uv add pykit-storage-s3
# or
pip install pykit-storage-s3
```

## Quick start

```python
from pykit_storage import StorageConfig
from pykit_storage_s3 import S3Storage

payload = b"hello"

storage = S3Storage(
    StorageConfig(
        provider="s3",
        bucket="app-objects",
        region="us-east-1",
    )
)

await storage.upload("images/photo.jpg", payload)
data = await storage.download("images/photo.jpg")
assert data == payload
```

## Registering the backend

Use `register(registry)` when your application selects storage backends through a `StorageRegistry`.

```python
from pykit_storage import StorageConfig, StorageRegistry
from pykit_storage_s3 import register as register_s3

registry = StorageRegistry()
register_s3(registry)

storage = registry.create(StorageConfig(provider="s3", bucket="app-objects", region="us-east-1"))
```

## What this package provides

- `S3Storage` for async upload, download, delete, exists, list, `url`, and `signed_url` operations
- `register(registry)` to register the `"s3"` backend explicitly
- `validate_key(path)` to validate normalized relative object keys

## Configuration notes

- `bucket` is required.
- AWS settings come from `StorageConfig`, including `region`, `endpoint_url`, `access_key_id`, and `secret_access_key`.
- `signed_url()` enforces the `signed_url_max_seconds` limit from `StorageConfig`.
- `url()` returns an `s3://` URL for the object.
