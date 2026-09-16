# pykit-vectorstore

Store and search embeddings through a vector API with an in-memory default, tenant-aware filters, and optional Qdrant registration.

## Installation

```bash
pip install pykit-vectorstore
pip install pykit-vectorstore-qdrant  # optional Qdrant adapter

uv add pykit-vectorstore
uv add pykit-vectorstore-qdrant  # optional Qdrant adapter
```

## Quick start

```python
from pykit_vectorstore import InMemoryVectorStore, PointPayload, SearchFilter

store = InMemoryVectorStore()
await store.ensure_collection("docs", dimensions=384, metric="cosine")
await store.upsert(
    "docs",
    id="doc-1",
    vector=[0.1, 0.2, 0.3],
    payload=PointPayload(fields={"tenant_id": "tenant-a", "lang": "en"}),
)

results = await store.search(
    "docs",
    vector=[0.15, 0.25, 0.35],
    limit=5,
    filter=SearchFilter().for_tenant("tenant-a").must_match("lang", "en"),
)
```

## Registering the Qdrant adapter

```python
from pykit_vectorstore import VectorStoreConfig, VectorStoreRegistry, register_memory
from pykit_vectorstore_qdrant import register as register_qdrant

registry = VectorStoreRegistry()
register_memory(registry)
register_qdrant(registry)

store = registry.create(VectorStoreConfig(backend="qdrant", metric="cosine"))
```

Importing `pykit_vectorstore` does not import Qdrant. The optional adapter fails only when it is constructed without `qdrant-client` installed.

## Core APIs

- **`VectorStore`** defines `ensure_collection`, `upsert`, `search`, and `delete`.
- **`VectorStoreRegistry`** is an injected backend registry. Empty registries have no backends.
- **`SearchFilter`** normalizes filter conditions and supports tenant isolation with `for_tenant()`.
- **`PointPayload`** and **`SearchResult`** carry stored metadata and search results.
- **`InMemoryVectorStore`** is a deterministic linear-scan backend for tests and prototypes.
- **`VectorStoreConfig`** captures backend and metric settings.

## See also

- [Main pykit README](../../../README.md)
- [tests/](tests/)
