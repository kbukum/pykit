"""Tests for embedding providers."""

from __future__ import annotations

import json

import httpx
import pytest

from pykit_ai import Model
from pykit_embedding import EmbeddingError, EmbeddingProvider, EmbedRequest, InMemoryProvider, Text
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


def _embedding_response(vectors: list[list[float]]) -> dict[str, object]:
    return {
        "object": "list",
        "data": [{"object": "embedding", "index": i, "embedding": v} for i, v in enumerate(vectors)],
        "model": "text-embedding-3-small",
        "usage": {"prompt_tokens": 10, "total_tokens": 10},
    }


async def test_in_memory_provider_is_deterministic() -> None:
    provider = InMemoryProvider(dimensions=3)
    req = EmbedRequest(model=Model(name="test"), inputs=[Text(text="hello")])
    first = await provider.embed(req)
    second = await provider.embed(req)
    assert first == second
    assert first.embeddings[0].dimensions == 3
    assert first.model.name == "test"


async def test_in_memory_embed_batch() -> None:
    provider = InMemoryProvider(dimensions=2)
    responses = await provider.embed_batch([EmbedRequest(model=Model(name="test"), inputs=[Text(text="a")])])
    assert len(responses) == 1
    assert len(responses[0].embeddings[0].vector) == 2


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
            result = await provider.embed(
                EmbedRequest(model=Model(name="text-embedding-3-small"), inputs=[Text(text="hello")])
            )
            assert len(result.embeddings) == 1
            assert result.embeddings[0].vector == [0.1, 0.2, 0.3]
            assert result.model.name == "text-embedding-3-small"
            assert result.usage.input_tokens == 10
        finally:
            await provider.close()

    async def test_embed_batch(self, config: OpenAIConfig) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert len(body["input"]) == 2
            return httpx.Response(200, json=_embedding_response([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]))

        provider = OpenAIEmbeddingProvider(config, client=_make_client(handler))
        try:
            result = await provider.embed(
                EmbedRequest(
                    model=Model(name="text-embedding-3-small"),
                    inputs=[Text(text="hello"), Text(text="world")],
                )
            )
            assert len(result.embeddings) == 2
        finally:
            await provider.close()

    async def test_embed_empty(self, config: OpenAIConfig) -> None:
        provider = OpenAIEmbeddingProvider(config)
        try:
            result = await provider.embed(EmbedRequest(model=Model(name="text-embedding-3-small"), inputs=[]))
            assert result.embeddings == []
        finally:
            await provider.close()

    async def test_api_error(self, config: OpenAIConfig) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="Internal Server Error")

        provider = OpenAIEmbeddingProvider(config, client=_make_client(handler))
        try:
            with pytest.raises(EmbeddingError) as exc_info:
                await provider.embed(
                    EmbedRequest(model=Model(name="text-embedding-3-small"), inputs=[Text(text="hello")])
                )
            assert exc_info.value.retryable is True
        finally:
            await provider.close()

    async def test_auth_error(self, config: OpenAIConfig) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, text="Unauthorized")

        provider = OpenAIEmbeddingProvider(config, client=_make_client(handler))
        try:
            with pytest.raises(EmbeddingError) as exc_info:
                await provider.embed(
                    EmbedRequest(model=Model(name="text-embedding-3-small"), inputs=[Text(text="hello")])
                )
            assert exc_info.value.retryable is False
        finally:
            await provider.close()

    def test_implements_protocol(self, config: OpenAIConfig) -> None:
        provider = OpenAIEmbeddingProvider(config)
        assert isinstance(provider, EmbeddingProvider)
