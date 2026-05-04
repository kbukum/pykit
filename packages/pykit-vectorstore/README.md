# pykit-vectorstore

Vector similarity abstraction with an in-memory lean default, optional Qdrant adapter, explicit
backend registries, canonical metrics (`cosine`, `dot`, `l2`), and tenant-aware filters.

## Installation

```bash
pip install pykit-vectorstore
pip install 'pykit-vectorstore[qdrant]'  # optional Qdrant adapter

uv add pykit-vectorstore
uv add 'pykit-vectorstore[qdrant]'  # optional Qdrant adapter
```

## In-memory Quick Start

```python
from pykit_vectorstore import InMemoryVectorStore, PointPayload, SearchFilter

store = InMemoryVectorStore()
await store.ensure_collection("docs", dimensions=384, metric="cosine")
await store.upsert(
    "docs",
    id="doc-1",
    vector=[0.1, 0.2, ...],
    payload=PointPayload(fields={"tenant_id": "tenant-a", "lang": "en"}),
)

results = await store.search(
    "docs",
    vector=[0.15, 0.25, ...],
    limit=5,
    filter=SearchFilter().for_tenant("tenant-a").must_match("lang", "en"),
)
```

## Config-driven selection and Qdrant registration

```python
from pykit_vectorstore import VectorStoreConfig, VectorStoreRegistry, register_memory
from pykit_vectorstore.qdrant import register as register_qdrant

registry = VectorStoreRegistry()
register_memory(registry)
register_qdrant(registry)

store = registry.create(VectorStoreConfig(backend="qdrant", metric="cosine"))
```

Importing `pykit_vectorstore` does not import Qdrant. The optional adapter fails only when
constructed without `qdrant-client` installed.

## Key Components

- **VectorStore** — async protocol: `ensure_collection`, `upsert`, `search`, `delete`.
- **VectorStoreRegistry** — injected backend registry; empty registries have no backends.
- **SearchFilter** — normalized filter conditions plus tenant isolation via `for_tenant()`.
- **InMemoryVectorStore** — deterministic linear-scan backend for tests/prototyping.
- **QdrantVectorStore** — optional adapter in `pykit_vectorstore.qdrant`.
