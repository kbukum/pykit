# pykit-vectorstore-qdrant

Qdrant backend for `pykit-vectorstore`.

## Installation

```bash
uv add pykit-vectorstore-qdrant
# or
pip install pykit-vectorstore-qdrant
```

## Quick start

```python
from pykit_vectorstore import PointPayload
from pykit_vectorstore_qdrant import QdrantConfig, QdrantVectorStore

store = QdrantVectorStore(QdrantConfig(url="http://localhost:6333", metric="cosine"))

await store.ensure_collection("docs", dimensions=3)
await store.upsert(
    "docs",
    id="doc-1",
    vector=[0.1, 0.2, 0.3],
    payload=PointPayload(fields={"tenant_id": "tenant-a", "lang": "en"}),
)
```

## Registering the backend

Use `register(registry)` when your application selects vector stores through a `VectorStoreRegistry`.

```python
from pykit_vectorstore import VectorStoreConfig, VectorStoreRegistry
from pykit_vectorstore_qdrant import register as register_qdrant

registry = VectorStoreRegistry()
register_qdrant(registry)

store = registry.create(VectorStoreConfig(backend="qdrant", metric="cosine"))
```

## What this package provides

- `QdrantVectorStore` for `ensure_collection`, `upsert`, `search`, and `delete`
- `QdrantConfig` with `url`, optional `api_key`, and `metric`
- `register(registry)` to register the `"qdrant"` backend explicitly

## Configuration notes

- Supported metrics are `cosine`, `dot`, and `l2`.
- The adapter validates an existing collection's dimensions and metric before reusing it.
- Missing `qdrant-client` support fails when the adapter is constructed, not when the package is imported.
