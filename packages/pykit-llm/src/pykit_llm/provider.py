"""LLM provider protocol — the universal interface for completions.

The canonical ``Provider`` Protocol natively satisfies pykit-provider's
``RequestResponse[CompletionRequest, CompletionResponse]`` shape via
``execute`` and exposes streaming via the named ``stream`` /
``execute_stream`` methods. Implementations may inherit ``ProviderBase`` to
pick up the default aliases and ``Component`` lifecycle, or implement the
methods directly.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from pykit_ai import Capabilities, Message, StreamEvent
from pykit_ai import count_tokens_approx as ai_count_tokens_approx
from pykit_component import Health, HealthStatus
from pykit_llm.types import CompletionRequest, CompletionResponse, StreamChunk
from pykit_provider import RequestResponse

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

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Return a completion for the supplied request."""

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        """Yield streamed completion chunks for the supplied request."""


@runtime_checkable
class Provider(RequestResponse[CompletionRequest, CompletionResponse], Protocol):
    """Enhanced provider protocol with capabilities and token counting.

    Natively implements pykit-provider's ``RequestResponse`` shape (via
    ``execute``) and exposes streaming via the named ``stream`` /
    ``execute_stream`` methods. It also carries pykit-component's
    ``Component`` lifecycle (``name``, ``start``, ``stop``, ``health``).
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

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Return a completion for the supplied request."""

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamEvent]:
        """Yield streamed events for the supplied request."""

    async def execute(self, input: CompletionRequest) -> CompletionResponse:
        """Execute a single completion request and return its response."""

    async def execute_stream(self, input: CompletionRequest) -> AsyncIterator[StreamEvent]:
        """Execute a completion request and yield streaming events."""

    def capabilities(self) -> Capabilities:
        """Describe the features supported by this provider."""

    def count_tokens(self, messages: list[Message]) -> int:
        """Estimate the token count for the provided messages."""


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
