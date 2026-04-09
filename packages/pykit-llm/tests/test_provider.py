"""Tests for Provider protocol and Capabilities."""

from __future__ import annotations

from collections.abc import AsyncIterator

from pykit_llm.provider import Capabilities, Provider, count_tokens_approx
from pykit_llm.stream_events import ContentDelta, StreamEvent
from pykit_llm.types import (
    AssistantMessage,
    CompletionRequest,
    CompletionResponse,
    Message,
    Usage,
    system,
    user,
)


class TestCapabilities:
    """Capabilities dataclass."""

    def test_defaults(self) -> None:
        c = Capabilities()
        assert c.supports_tools is False
        assert c.supports_vision is False
        assert c.supports_thinking is False
        assert c.supports_streaming is False
        assert c.max_context_tokens == 0
        assert c.max_output_tokens == 0
        assert c.model_id == ""

    def test_custom_values(self) -> None:
        c = Capabilities(
            supports_tools=True,
            supports_vision=True,
            supports_thinking=True,
            supports_streaming=True,
            max_context_tokens=128_000,
            max_output_tokens=4096,
            model_id="gpt-4o",
        )
        assert c.supports_tools is True
        assert c.max_context_tokens == 128_000
        assert c.model_id == "gpt-4o"


class TestProviderProtocol:
    """Provider protocol conformance."""

    def test_concrete_class_satisfies_protocol(self) -> None:
        class MockProvider:
            async def complete(self, request: CompletionRequest) -> CompletionResponse:
                return CompletionResponse(message=AssistantMessage())

            async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamEvent]:
                yield ContentDelta(text="hi")

            def capabilities(self) -> Capabilities:
                return Capabilities(model_id="mock")

            def count_tokens(self, messages: list[Message]) -> int:
                return 42

        p = MockProvider()
        assert isinstance(p, Provider)

    def test_missing_method_fails_protocol(self) -> None:
        class IncompleteProvider:
            async def complete(self, request: CompletionRequest) -> CompletionResponse:
                return CompletionResponse(message=AssistantMessage())

        p = IncompleteProvider()
        assert not isinstance(p, Provider)


class TestCountTokensApprox:
    """Approximate token counter utility."""

    def test_empty_messages(self) -> None:
        assert count_tokens_approx([]) == 0

    def test_user_message(self) -> None:
        msgs: list[Message] = [user("hello world")]
        # "hello world" = 11 chars => 11 // 4 = 2
        assert count_tokens_approx(msgs) == 2

    def test_system_message(self) -> None:
        msgs: list[Message] = [system("You are a helpful assistant.")]
        # 28 chars => 28 // 4 = 7
        assert count_tokens_approx(msgs) == 7

    def test_multiple_messages(self) -> None:
        msgs: list[Message] = [
            system("system prompt"),  # 13 chars
            user("hello"),  # 5 chars
        ]
        # total = 18, 18 // 4 = 4
        assert count_tokens_approx(msgs) == 4

    def test_assistant_message(self) -> None:
        from pykit_llm.types import TextBlock

        msgs: list[Message] = [
            AssistantMessage(content=[TextBlock(text="response text")])
        ]
        # 13 chars => 13 // 4 = 3
        assert count_tokens_approx(msgs) == 3
