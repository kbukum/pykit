# pykit-vectorstore

Vector similarity search store with in-memory and Qdrant backends, builder-pattern filters, and cosine similarity.

## Installation

```bash
pip install pykit-vectorstore
# or
uv add pykit-vectorstore

# With Qdrant backend
pip install pykit-vectorstore[qdrant]
```

## Quick Start

```python
from pykit_vectorstore import (
    InMemoryVectorStore, PointPayload, SearchFilter, VectorStore,
)

store: VectorStore = InMemoryVectorStore()
await store.ensure_collection("docs", dimensions=384)

# Upsert vectors with metadata
payload = PointPayload().with_field("title", "Introduction").with_field("lang", "en")
await store.upsert("docs", id="doc-1", vector=[0.1, 0.2, ...], payload=payload)

# Search with optional filtering
results = await store.search(
    "docs",
    vector=[0.15, 0.25, ...],
    limit=5,
    filter=SearchFilter().must_match("lang", "en"),
)
for r in results:
    print(f"{r.id}: score={r.score:.3f}, title={r.payload.fields['title']}")
```

### Qdrant Backend

```python
from pykit_vectorstore.qdrant import QdrantVectorStore, QdrantConfig

store = QdrantVectorStore(QdrantConfig(url="http://localhost:6333"))
await store.ensure_collection("embeddings", dimensions=768)
```

## Key Components

- **VectorStore** — Protocol defining the async vector store interface: `ensure_collection`, `upsert`, `search`, `delete`
- **PointPayload** — Metadata stored with each vector, with fluent `with_field()` builder
- **SearchResult** — Search result with `id`, `score`, and `payload`
- **SearchFilter** — Optional query filter with fluent `must_match()` builder
- **InMemoryVectorStore** — Thread-safe in-memory implementation using cosine similarity (for testing/prototyping)
- **QdrantVectorStore** — Production backend using Qdrant with cosine distance metric
- **VectorStoreError** — Raised on vector store operation failures

## Dependencies

- `numpy`
- Optional: `qdrant-client` (qdrant extra)

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
