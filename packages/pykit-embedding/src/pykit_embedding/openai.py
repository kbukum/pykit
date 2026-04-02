"""OpenAI-compatible embedding provider backed by httpx."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from pykit_embedding.provider import EmbeddingError


@dataclass
class OpenAIEmbeddingConfig:
    """Configuration for the OpenAI-compatible embedding provider.

    Works with OpenAI, Azure OpenAI, local llama.cpp, vLLM, or any server
    that exposes the ``/v1/embeddings`` endpoint.
    """

    endpoint: str = "https://api.openai.com"
    api_key: str = ""
    model: str = "text-embedding-3-small"
    dimensions: int = 1536


class OpenAIEmbeddingProvider:
    """OpenAI-compatible embedding provider.

    Implements the :class:`~pykit_embedding.provider.EmbeddingProvider` protocol.
    """

    def __init__(
        self,
        config: OpenAIEmbeddingConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config = config
        kwargs: dict[str, Any] = {
            "base_url": config.endpoint,
            "timeout": 120.0,
        }
        if config.api_key:
            kwargs["headers"] = {
                "authorization": f"Bearer {config.api_key}",
                "content-type": "application/json",
            }
        if transport is not None:
            kwargs["transport"] = transport
        self._client = httpx.AsyncClient(**kwargs)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for the given texts."""
        if not texts:
            return []

        payload: dict[str, Any] = {
            "model": self._config.model,
            "input": texts,
        }

        try:
            resp = await self._client.post("/v1/embeddings", json=payload)
        except httpx.HTTPError as exc:
            raise EmbeddingError(f"embedding request failed: {exc}", retryable=True) from exc

        if resp.status_code != 200:
            retryable = resp.status_code >= 500 or resp.status_code == 429
            raise EmbeddingError(
                f"embedding API returned HTTP {resp.status_code}: {resp.text}",
                retryable=retryable,
            )

        data = resp.json()
        results: list[list[float]] = []
        for item in sorted(data.get("data", []), key=lambda x: x.get("index", 0)):
            results.append(item["embedding"])

        return results

    def dimensions(self) -> int:
        """Return the configured embedding dimensions."""
        return self._config.dimensions

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
