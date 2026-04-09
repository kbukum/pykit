"""LLM provider protocol — the universal interface for completions."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from pykit_llm.stream_events import StreamEvent
from pykit_llm.types import CompletionRequest, CompletionResponse, Message, StreamChunk


@dataclass
class Capabilities:
    """Describes what a provider supports."""

    supports_tools: bool = False
    supports_vision: bool = False
    supports_thinking: bool = False
    supports_streaming: bool = False
    max_context_tokens: int = 0
    max_output_tokens: int = 0
    model_id: str = ""


@runtime_checkable
class LLMProvider(Protocol):
    """Any backend that can produce chat completions."""

    async def complete(self, request: CompletionRequest) -> CompletionResponse: ...

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]: ...


@runtime_checkable
class Provider(Protocol):
    """Enhanced provider protocol with capabilities and token counting."""

    async def complete(self, request: CompletionRequest) -> CompletionResponse: ...

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamEvent]: ...

    def capabilities(self) -> Capabilities: ...

    def count_tokens(self, messages: list[Message]) -> int: ...


def count_tokens_approx(messages: list[Message]) -> int:
    """Approximate token count based on ~4 characters per token.

    Args:
        messages: List of messages to estimate token count for.

    Returns:
        Approximate token count.
    """
    total_chars = 0
    for msg in messages:
        match msg:
            case m if hasattr(m, "content") and isinstance(m.content, str):
                total_chars += len(m.content)
            case m if hasattr(m, "content") and isinstance(m.content, list):
                from pykit_llm.types import TextBlock

                for block in m.content:
                    if isinstance(block, TextBlock):
                        total_chars += len(block.text)
    return total_chars // 4
