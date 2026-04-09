"""OpenAI-compatible embedding provider using pykit-httpclient."""

from __future__ import annotations

from typing import Any

from pykit_embedding.provider import EmbeddingError
from pykit_httpclient import AuthConfig, HttpClient, HttpConfig, HttpError
from pykit_llm_providers.openai.config import OpenAIConfig


class OpenAIEmbeddingProvider:
    """OpenAI-compatible embedding provider using pykit-httpclient.

    Implements the :class:`~pykit_embedding.provider.EmbeddingProvider` protocol.
    Works with OpenAI, Azure OpenAI, local llama.cpp, vLLM, or any server
    that exposes the ``/v1/embeddings`` endpoint.
    """

    def __init__(
        self,
        config: OpenAIConfig,
        *,
        client: HttpClient | None = None,
    ) -> None:
        self._config = config
        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            http_config = HttpConfig(
                name="openai-embedding",
                base_url=config.base_url or "https://api.openai.com/v1",
                timeout=config.timeout,
                auth=AuthConfig(type="bearer", token=config.api_key) if config.api_key else None,
            )
            self._client = HttpClient(http_config)
            self._owns_client = True

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for the given texts."""
        if not texts:
            return []

        payload: dict[str, Any] = {
            "model": self._config.embedding_model,
            "input": texts,
        }

        try:
            resp = await self._client.post("/embeddings", body=payload)
        except HttpError as exc:
            retryable = exc.retryable
            raise EmbeddingError(
                f"embedding request failed: {exc}",
                retryable=retryable,
            ) from exc
        except Exception as exc:
            raise EmbeddingError(
                f"embedding request failed: {exc}",
                retryable=True,
            ) from exc

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
        if self._owns_client:
            await self._client.close()
