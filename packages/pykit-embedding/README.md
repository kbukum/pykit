# pykit-embedding

Embedding provider abstractions with distance metrics, pooling functions, and an OpenAI-compatible implementation.

## Installation

```bash
pip install pykit-embedding
# or
uv add pykit-embedding
```

## Quick Start

```python
import asyncio
from pykit_embedding import (
    OpenAIEmbeddingConfig, OpenAIEmbeddingProvider,
    cosine_similarity, mean_pooling, Embedding,
)

config = OpenAIEmbeddingConfig(
    endpoint="https://api.openai.com",
    api_key="sk-...",
    model="text-embedding-3-small",
    dimensions=1536,
)
provider = OpenAIEmbeddingProvider(config)

async def main():
    vectors = await provider.embed(["Hello world", "Goodbye world"])
    similarity = cosine_similarity(vectors[0], vectors[1])
    print(f"Similarity: {similarity:.4f}")

    # Aggregate multiple vectors
    pooled = mean_pooling(vectors)
    await provider.close()

asyncio.run(main())
```

## Key Components

- **EmbeddingProvider** — Runtime-checkable protocol: `async embed(texts) -> list[list[float]]` and `dimensions() -> int`
- **OpenAIEmbeddingProvider** — OpenAI-compatible implementation that works with OpenAI, Azure OpenAI, llama.cpp, vLLM, or any `/v1/embeddings` endpoint
- **OpenAIEmbeddingConfig** — Configuration: `endpoint`, `api_key`, `model`, `dimensions`
- **Embedding** — Dataclass with `vector`, optional `text` and `model`, and a `dims` property
- **cosine_similarity(a, b)** — Cosine similarity between two vectors (range: -1.0 to 1.0)
- **euclidean_distance(a, b)** — L2 distance between two vectors
- **dot_product(a, b)** — Dot product of two vectors
- **mean_pooling(vectors)** — Element-wise mean of multiple vectors
- **max_pooling(vectors)** — Element-wise maximum of multiple vectors
- **EmbeddingError** — Exception with `retryable` flag for transient error handling

## Dependencies

- `httpx` — Async HTTP client
- `numpy` — Numerical operations

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
