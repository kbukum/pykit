# pykit-storage

Async object-storage abstraction with pluggable backends for local filesystem and S3.

## Installation

```bash
pip install pykit-storage
# or
uv add pykit-storage

# With S3 support
pip install pykit-storage[s3]
```

## Quick Start

```python
from pykit_storage import StorageConfig, StorageComponent

# Local filesystem storage
config = StorageConfig(provider="local", base_path="./uploads", public_url="/files")
component = StorageComponent(config)
await component.start()

storage = component.storage
await storage.upload("images/photo.jpg", image_bytes)
exists = await storage.exists("images/photo.jpg")     # True
data = await storage.download("images/photo.jpg")      # bytes
url = await storage.url("images/photo.jpg")            # "/files/images/photo.jpg"

files = await storage.list(prefix="images/")           # [FileInfo(...), ...]
for f in files:
    print(f"{f.path} — {f.size} bytes, {f.content_type}")

await storage.delete("images/photo.jpg")
health = await component.health()
await component.stop()
```

## Key Components

- **Storage** — Protocol defining the async storage interface: `upload`, `download`, `delete`, `exists`, `list`, `url`
- **FileInfo** — Frozen dataclass with file metadata: `path`, `size`, `last_modified`, `content_type`
- **LocalStorage** — Local filesystem implementation using `aiofiles`
- **StorageConfig** — Configuration: `provider` ("local" or "s3"), `base_path`, `max_file_size`, `public_url`, `allowed_types`
- **StorageComponent** — Lifecycle-managed component with `start()`, `stop()`, `health()` (implements Component protocol)

## Dependencies

- `pykit-errors`, `pykit-component`
- `aiofiles`
- Optional: `aioboto3` (s3 extra)

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
