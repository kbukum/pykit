"""Tests for embedding providers (using pykit-llm-providers vendor module)."""

from __future__ import annotations

import json

import httpx
import pytest

from pykit_embedding.provider import EmbeddingError, EmbeddingProvider
from pykit_httpclient import AuthConfig, HttpClient, HttpConfig
from pykit_llm_providers.openai import OpenAIConfig, OpenAIEmbeddingProvider


def _mock_transport(handler):
    return httpx.MockTransport(handler)


def _make_client(handler) -> HttpClient:
    config = HttpConfig(
        name="test-embedding",
        base_url="https://api.openai.com/v1",
        timeout=30.0,
        auth=AuthConfig(type="bearer", token="sk-test"),
    )
    return HttpClient(config, transport=_mock_transport(handler))


def _embedding_response(vectors: list[list[float]]) -> dict:
    return {
        "object": "list",
        "data": [{"object": "embedding", "index": i, "embedding": v} for i, v in enumerate(vectors)],
        "model": "text-embedding-3-small",
        "usage": {"prompt_tokens": 10, "total_tokens": 10},
    }


class TestOpenAIEmbeddingProvider:
    @pytest.fixture
    def config(self) -> OpenAIConfig:
        return OpenAIConfig(
            api_key="sk-test",
            embedding_model="text-embedding-3-small",
            embedding_dimensions=3,
        )

    async def test_embed_single(self, config: OpenAIConfig) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert body["model"] == "text-embedding-3-small"
            assert body["input"] == ["hello"]
            return httpx.Response(200, json=_embedding_response([[0.1, 0.2, 0.3]]))

        provider = OpenAIEmbeddingProvider(config, client=_make_client(handler))
        try:
            result = await provider.embed(["hello"])
            assert len(result) == 1
            assert len(result[0]) == 3
            assert abs(result[0][0] - 0.1) < 1e-6
        finally:
            await provider.close()

    async def test_embed_batch(self, config: OpenAIConfig) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert len(body["input"]) == 2
            return httpx.Response(
                200,
                json=_embedding_response([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]),
            )

        provider = OpenAIEmbeddingProvider(config, client=_make_client(handler))
        try:
            result = await provider.embed(["hello", "world"])
            assert len(result) == 2
        finally:
            await provider.close()

    async def test_embed_empty(self, config: OpenAIConfig) -> None:
        provider = OpenAIEmbeddingProvider(config)
        try:
            result = await provider.embed([])
            assert result == []
        finally:
            await provider.close()

    async def test_api_error(self, config: OpenAIConfig) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="Internal Server Error")

        provider = OpenAIEmbeddingProvider(config, client=_make_client(handler))
        try:
            with pytest.raises(EmbeddingError) as exc_info:
                await provider.embed(["hello"])
            assert exc_info.value.retryable is True
        finally:
            await provider.close()

    async def test_auth_error(self, config: OpenAIConfig) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, text="Unauthorized")

        provider = OpenAIEmbeddingProvider(config, client=_make_client(handler))
        try:
            with pytest.raises(EmbeddingError) as exc_info:
                await provider.embed(["hello"])
            assert exc_info.value.retryable is False
        finally:
            await provider.close()

    def test_dimensions(self, config: OpenAIConfig) -> None:
        provider = OpenAIEmbeddingProvider(config)
        assert provider.dimensions() == 3

    def test_implements_protocol(self, config: OpenAIConfig) -> None:
        provider = OpenAIEmbeddingProvider(config)
        assert isinstance(provider, EmbeddingProvider)
