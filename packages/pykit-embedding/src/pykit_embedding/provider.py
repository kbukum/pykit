"""Embedding provider protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class EmbeddingError(Exception):
    """Raised when an embedding operation fails."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for generating vector embeddings from text."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for a batch of text inputs."""
        ...

    def dimensions(self) -> int:
        """Return the dimensionality of the embedding vectors."""
        ...
