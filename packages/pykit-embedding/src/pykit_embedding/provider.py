"""Embedding provider protocol and deterministic in-memory adapter."""

from __future__ import annotations

import hashlib
import time
from typing import Protocol, runtime_checkable

from opentelemetry import trace
from opentelemetry.trace import Tracer

from pykit_ai import Usage
from pykit_ai.semconv import (
    GENAI_OPERATION_EMBEDDING,
    GENAI_OPERATION_NAME,
    GENAI_REQUEST_MODEL,
    GENAI_SYSTEM,
)
from pykit_component import Health, HealthStatus
from pykit_embedding.types import Audio, Embedding, EmbedRequest, EmbedResponse, Image, Text, Video
from pykit_provider import RequestResponse


class EmbeddingError(Exception):
    """Raised when an embedding operation fails."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


@runtime_checkable
class Provider(RequestResponse[EmbedRequest, EmbedResponse], Protocol):
    """Canonical embedding provider.

    Natively satisfies pykit-provider ``RequestResponse[EmbedRequest,
    EmbedResponse]`` (via ``execute``) and pykit-component ``Component``
    lifecycle.
    """

    @property
    def name(self) -> str:
        """Return the provider's stable name."""

    async def is_available(self) -> bool:
        """Report whether the provider can currently serve requests."""

    async def start(self) -> None:
        """Initialize provider resources before handling requests."""

    async def stop(self) -> None:
        """Release provider resources and stop serving requests."""

    async def health(self) -> Health:
        """Return the provider's current health status."""

    async def embed(self, req: EmbedRequest) -> EmbedResponse:
        """Create embeddings for the request inputs."""

    async def embed_batch(self, reqs: list[EmbedRequest]) -> list[EmbedResponse]:
        """Create embeddings for each request in the batch."""

    async def execute(self, input: EmbedRequest) -> EmbedResponse:
        """Execute a single embedding request and return its response."""


class ProviderBase:
    """Shared lifecycle/touch wiring for embedding providers."""

    _name: str = "embedding"

    def __init__(self, *, tracer: Tracer | None = None) -> None:
        self._last_call_at: float = 0.0
        self._started: bool = False
        self._tracer = tracer or trace.NoOpTracer()

    @property
    def name(self) -> str:
        return self._name

    async def is_available(self) -> bool:
        return True

    async def start(self) -> None:
        self._started = True

    async def stop(self) -> None:
        self._started = False

    async def health(self) -> Health:
        status = HealthStatus.HEALTHY if self._started else HealthStatus.UNHEALTHY
        return Health(name=self._name, status=status, message=f"last_call_at={self._last_call_at:.3f}")

    def _touch(self) -> None:
        self._last_call_at = time.monotonic()


class InMemoryProvider(ProviderBase):
    """Deterministic in-memory embedding adapter for tests."""

    _name = "in-memory"

    def __init__(self, *, dimensions: int = 8, tracer: Tracer | None = None) -> None:
        super().__init__(tracer=tracer)
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self._dimensions = dimensions

    async def embed(self, req: EmbedRequest) -> EmbedResponse:
        with self._tracer.start_as_current_span("embedding.embed") as span:
            span.set_attribute(GENAI_SYSTEM, "in_memory")
            span.set_attribute(GENAI_OPERATION_NAME, GENAI_OPERATION_EMBEDDING)
            span.set_attribute(GENAI_REQUEST_MODEL, req.model.name)
            span.set_attribute("embedding.input_count", len(req.inputs))
            self._touch()
            embeddings = [
                Embedding(
                    vector=_vector_for_input(input_, self._dimensions),
                    dimensions=self._dimensions,
                    index=index,
                )
                for index, input_ in enumerate(req.inputs)
            ]
            return EmbedResponse(embeddings=embeddings, model=req.model, usage=Usage())

    async def embed_batch(self, reqs: list[EmbedRequest]) -> list[EmbedResponse]:
        return [await self.embed(req) for req in reqs]

    async def execute(self, input: EmbedRequest) -> EmbedResponse:
        return await self.embed(input)


def _input_bytes(input_: Text | Image | Audio | Video) -> bytes:
    match input_:
        case Text(text=text):
            return text.encode("utf-8")
        case Image(data=data, url=url) | Audio(data=data, url=url) | Video(data=data, url=url):
            return data if data is not None else (url or "").encode("utf-8")
        case _:
            raise ValueError(f"Unsupported embedding input type: {type(input_).__name__}")


def _vector_for_input(input_: Text | Image | Audio | Video, dimensions: int) -> list[float]:
    digest = hashlib.sha256(_input_bytes(input_)).digest()
    values: list[float] = []
    while len(values) < dimensions:
        for byte in digest:
            values.append((byte / 127.5) - 1.0)
            if len(values) == dimensions:
                break
        digest = hashlib.sha256(digest).digest()
    return values


EmbeddingProvider = Provider
