"""Tests for embedding providers."""

from __future__ import annotations

import json

import httpx
import pytest

from pykit_embedding.openai import OpenAIEmbeddingConfig, OpenAIEmbeddingProvider
from pykit_embedding.provider import EmbeddingError, EmbeddingProvider


def _mock_transport(handler):
    return httpx.MockTransport(handler)


def _embedding_response(vectors: list[list[float]]) -> dict:
    return {
        "object": "list",
        "data": [{"object": "embedding", "index": i, "embedding": v} for i, v in enumerate(vectors)],
        "model": "text-embedding-3-small",
        "usage": {"prompt_tokens": 10, "total_tokens": 10},
    }


class TestOpenAIEmbeddingProvider:
    @pytest.fixture
    def config(self) -> OpenAIEmbeddingConfig:
        return OpenAIEmbeddingConfig(
            endpoint="https://api.openai.com",
            api_key="sk-test",
            model="text-embedding-3-small",
            dimensions=3,
        )

    async def test_embed_single(self, config: OpenAIEmbeddingConfig) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert body["model"] == "text-embedding-3-small"
            assert body["input"] == ["hello"]
            return httpx.Response(200, json=_embedding_response([[0.1, 0.2, 0.3]]))

        provider = OpenAIEmbeddingProvider(config, transport=_mock_transport(handler))
        try:
            result = await provider.embed(["hello"])
            assert len(result) == 1
            assert len(result[0]) == 3
            assert abs(result[0][0] - 0.1) < 1e-6
        finally:
            await provider.close()

    async def test_embed_batch(self, config: OpenAIEmbeddingConfig) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert len(body["input"]) == 2
            return httpx.Response(
                200,
                json=_embedding_response([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]),
            )

        provider = OpenAIEmbeddingProvider(config, transport=_mock_transport(handler))
        try:
            result = await provider.embed(["hello", "world"])
            assert len(result) == 2
        finally:
            await provider.close()

    async def test_embed_empty(self, config: OpenAIEmbeddingConfig) -> None:
        provider = OpenAIEmbeddingProvider(
            config, transport=_mock_transport(lambda r: httpx.Response(200, json=_embedding_response([])))
        )
        try:
            result = await provider.embed([])
            assert result == []
        finally:
            await provider.close()

    async def test_api_error(self, config: OpenAIEmbeddingConfig) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="Internal Server Error")

        provider = OpenAIEmbeddingProvider(config, transport=_mock_transport(handler))
        try:
            with pytest.raises(EmbeddingError) as exc_info:
                await provider.embed(["hello"])
            assert exc_info.value.retryable is True
        finally:
            await provider.close()

    async def test_auth_error(self, config: OpenAIEmbeddingConfig) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, text="Unauthorized")

        provider = OpenAIEmbeddingProvider(config, transport=_mock_transport(handler))
        try:
            with pytest.raises(EmbeddingError) as exc_info:
                await provider.embed(["hello"])
            assert exc_info.value.retryable is False
        finally:
            await provider.close()

    def test_dimensions(self, config: OpenAIEmbeddingConfig) -> None:
        provider = OpenAIEmbeddingProvider(config)
        assert provider.dimensions() == 3

    def test_implements_protocol(self, config: OpenAIEmbeddingConfig) -> None:
        provider = OpenAIEmbeddingProvider(config)
        assert isinstance(provider, EmbeddingProvider)
