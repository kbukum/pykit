"""OpenAI-compatible embedding provider using pykit-httpclient."""

from __future__ import annotations

from typing import Any

from opentelemetry.trace import Tracer

from pykit_ai import Model, Provider, Usage
from pykit_ai.semconv import (
    GENAI_OPERATION_EMBEDDING,
    GENAI_OPERATION_NAME,
    GENAI_REQUEST_MODEL,
    GENAI_SYSTEM,
)
from pykit_embedding import Embedding, EmbeddingError, EmbedRequest, EmbedResponse, ProviderBase, Text
from pykit_httpclient import AuthConfig, HttpClient, HttpConfig, HttpError
from pykit_httpclient.types import Response
from pykit_llm_openai.config import OpenAIConfig
from pykit_resilience import Policy


class OpenAIEmbeddingProvider(ProviderBase):
    """OpenAI-compatible canonical embedding provider."""

    _name = "openai-embedding"

    def __init__(
        self,
        config: OpenAIConfig,
        *,
        client: HttpClient | None = None,
        tracer: Tracer | None = None,
        policy: Policy | None = None,
    ) -> None:
        super().__init__(tracer=tracer)
        self._config = config
        self._policy = policy
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

    async def embed(self, req: EmbedRequest) -> EmbedResponse:
        """Generate embeddings for a canonical embedding request."""
        with self._tracer.start_as_current_span("embedding.embed") as span:
            span.set_attribute(GENAI_SYSTEM, "openai")
            span.set_attribute(GENAI_OPERATION_NAME, GENAI_OPERATION_EMBEDDING)
            span.set_attribute(GENAI_REQUEST_MODEL, req.model.name or self._config.embedding_model)
            span.set_attribute("embedding.input_count", len(req.inputs))
            self._touch()
            texts: list[str] = []
            for input_ in req.inputs:
                if not isinstance(input_, Text):
                    raise EmbeddingError(
                        "OpenAI embedding adapter supports text inputs only", retryable=False
                    )
                texts.append(input_.text)
            if not texts:
                return EmbedResponse(embeddings=[], model=req.model, usage=Usage())

            payload: dict[str, Any] = {
                "model": req.model.name or self._config.embedding_model,
                "input": texts,
            }
            payload.update(req.options)

            async def _call() -> Response:
                return await self._client.post("/embeddings", body=payload)

            try:
                resp = await _call() if self._policy is None else await self._policy.execute(_call)
            except HttpError as exc:
                raise EmbeddingError(f"embedding request failed: {exc}", retryable=exc.retryable) from exc

            data = resp.json()
            embeddings = [
                Embedding(
                    vector=[float(value) for value in item["embedding"]],
                    dimensions=len(item["embedding"]),
                    index=int(item.get("index", index)),
                )
                for index, item in enumerate(sorted(data.get("data", []), key=lambda x: x.get("index", 0)))
            ]
            usage_raw = data.get("usage", {})
            prompt_tokens = usage_raw.get("prompt_tokens", 0) if isinstance(usage_raw, dict) else 0
            model_name = data.get("model") if isinstance(data.get("model"), str) else req.model.name
            return EmbedResponse(
                embeddings=embeddings,
                model=Model(name=model_name, provider=Provider.OPENAI, version=req.model.version),
                usage=Usage(input_tokens=int(prompt_tokens)),
            )

    async def embed_batch(self, reqs: list[EmbedRequest]) -> list[EmbedResponse]:
        """Generate embeddings for multiple canonical requests."""
        return [await self.embed(req) for req in reqs]

    async def execute(self, input: EmbedRequest) -> EmbedResponse:
        return await self.embed(input)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._owns_client:
            await self._client.close()
