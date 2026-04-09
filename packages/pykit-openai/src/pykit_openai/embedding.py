"""OpenAI-compatible embedding provider backed by httpx."""

from __future__ import annotations

from typing import Any

import httpx

from pykit_embedding.provider import EmbeddingError
from pykit_openai.config import OpenAIConfig


class OpenAIEmbeddingProvider:
    """OpenAI-compatible embedding provider.

    Implements the :class:`~pykit_embedding.provider.EmbeddingProvider` protocol.
    Works with OpenAI, Azure OpenAI, local llama.cpp, vLLM, or any server
    that exposes the ``/v1/embeddings`` endpoint.
    """

    def __init__(
        self,
        config: OpenAIConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config = config
        base_url = config.base_url or "https://api.openai.com/v1"
        kwargs: dict[str, Any] = {
            "base_url": base_url,
            "timeout": config.timeout,
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
            "model": self._config.embedding_model,
            "input": texts,
        }

        try:
            resp = await self._client.post("/embeddings", json=payload)
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
        return self._config.embedding_dimensions

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
