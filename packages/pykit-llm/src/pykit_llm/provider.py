"""LLM provider protocol — the universal interface for completions.

The canonical ``Provider`` Protocol natively satisfies pykit-provider's
``RequestResponse[CompletionRequest, CompletionResponse]`` and
``Stream[CompletionRequest, StreamEvent]`` shapes via the ``execute`` and
``execute_stream`` methods, which alias ``complete`` and ``stream``
respectively. Implementations may inherit ``ProviderBase`` to pick up the
default aliases and ``Component`` lifecycle, or implement the methods directly.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from pykit_ai import Capabilities, Message, StreamEvent
from pykit_ai import count_tokens_approx as ai_count_tokens_approx
from pykit_component import Health, HealthStatus
from pykit_llm.types import CompletionRequest, CompletionResponse, StreamChunk

__all__ = [
    "Capabilities",
    "LLMProvider",
    "Provider",
    "ProviderBase",
    "count_tokens_approx",
]


@runtime_checkable
class LLMProvider(Protocol):
    """Any backend that can produce chat completions."""

    async def complete(self, request: CompletionRequest) -> CompletionResponse: ...

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]: ...


@runtime_checkable
class Provider(Protocol):
    """Enhanced provider protocol with capabilities and token counting.

    Natively implements pykit-provider's ``RequestResponse`` shape (via
    ``execute``) and ``Stream`` shape (via ``execute_stream``), and
    pykit-component's ``Component`` lifecycle (``name``, ``start``, ``stop``,
    ``health``). Drop-in compatible with dag/pipeline/chain/worker consumers.
    """

    @property
    def name(self) -> str: ...

    async def is_available(self) -> bool: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def health(self) -> Health: ...

    async def complete(self, request: CompletionRequest) -> CompletionResponse: ...

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamEvent]: ...

    async def execute(self, input: CompletionRequest) -> CompletionResponse: ...

    async def execute_stream(self, input: CompletionRequest) -> AsyncIterator[StreamEvent]: ...

    def capabilities(self) -> Capabilities: ...

    def count_tokens(self, messages: list[Message]) -> int: ...


class ProviderBase:
    """Mixin supplying ``execute``/``execute_stream`` aliases and ``Component`` lifecycle.

    Concrete LLM providers (OpenAI, Anthropic, Gemini) may inherit this to gain
    the canonical provider/component surface without re-implementing it. A
    ``last_call_at`` timestamp is updated on every ``complete``/``stream`` to
    feed the ``health()`` payload.

    Subclasses must implement ``complete`` and ``stream`` and set ``_name`` to
    the provider's stable identity (e.g. ``"openai"``).
    """

    _name: str = "llm"

    def __init__(self) -> None:
        self._last_call_at: float = 0.0
        self._started: bool = False

    @property
    def name(self) -> str:
        return self._name

    async def is_available(self) -> bool:
        return True

    async def start(self) -> None:
        self._started = True

    async def stop(self) -> None:
        self._started = False
        close = getattr(self, "close", None)
        if callable(close):
            await close()

    async def health(self) -> Health:
        status = HealthStatus.HEALTHY if self._started else HealthStatus.UNHEALTHY
        message = f"last_call_at={self._last_call_at:.3f}"
        return Health(name=self._name, status=status, message=message)

    def _touch(self) -> None:
        self._last_call_at = time.monotonic()

    async def execute(self, input: CompletionRequest) -> CompletionResponse:
        result: CompletionResponse = await self.complete(input)  # type: ignore[attr-defined]
        return result

    async def execute_stream(self, input: CompletionRequest) -> AsyncIterator[StreamEvent]:
        async for event in self.stream(input):  # type: ignore[attr-defined]
            yield event


def count_tokens_approx(messages: list[Message]) -> int:
    """Approximate token count using canonical AI message heuristics."""
    return ai_count_tokens_approx(messages)
