"""LLM provider protocol — the universal interface for completions."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from pykit_llm.types import CompletionRequest, CompletionResponse, StreamChunk


@runtime_checkable
class LLMProvider(Protocol):
    """Any backend that can produce chat completions."""

    async def complete(self, request: CompletionRequest) -> CompletionResponse: ...

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]: ...
