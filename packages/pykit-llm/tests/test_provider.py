"""Tests for Provider protocol and Capabilities."""

from __future__ import annotations

from collections.abc import AsyncIterator

from pykit_llm.provider import Capabilities, Provider, count_tokens_approx
from pykit_llm.stream_events import StreamEvent, TextDelta
from pykit_llm.types import (
    AssistantMessage,
    CompletionRequest,
    CompletionResponse,
    Message,
    system,
    user,
)


class TestCapabilities:
    """Capabilities dataclass."""

    def test_defaults(self) -> None:
        c = Capabilities()
        assert c.tool_use is False
        assert c.vision is False
        assert c.reasoning_tokens is False
        assert c.streaming is False
        assert c.max_input_tokens == 0
        assert c.max_output_tokens == 0

    def test_custom_values(self) -> None:
        c = Capabilities(
            tool_use=True,
            vision=True,
            reasoning_tokens=True,
            streaming=True,
            max_input_tokens=128_000,
            max_output_tokens=4096,
        )
        assert c.tool_use is True
        assert c.max_input_tokens == 128_000


class TestProviderProtocol:
    """Provider protocol conformance."""

    def test_concrete_class_satisfies_protocol(self) -> None:
        from pykit_component import Health, HealthStatus

        class MockProvider:
            name = "mock"

            async def is_available(self) -> bool:
                return True

            async def start(self) -> None:
                return None

            async def stop(self) -> None:
                return None

            async def health(self) -> Health:
                return Health(name="mock", status=HealthStatus.HEALTHY)

            async def complete(self, request: CompletionRequest) -> CompletionResponse:
                return CompletionResponse(message=AssistantMessage())

            async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamEvent]:
                yield TextDelta(text="hi")

            async def execute(self, input: CompletionRequest) -> CompletionResponse:
                return await self.complete(input)

            async def execute_stream(self, input: CompletionRequest) -> AsyncIterator[StreamEvent]:
                async for event in self.stream(input):
                    yield event

            def capabilities(self) -> Capabilities:
                return Capabilities()

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
        # 11 // 4 + 4 message framing tokens
        assert count_tokens_approx(msgs) == 6

    def test_system_message(self) -> None:
        msgs: list[Message] = [system("You are a helpful assistant.")]
        # 28 // 4 + 4 message framing tokens
        assert count_tokens_approx(msgs) == 11

    def test_multiple_messages(self) -> None:
        msgs: list[Message] = [
            system("system prompt"),  # 13 chars
            user("hello"),  # 5 chars
        ]
        # 13 // 4 + 4 plus 5 // 4 + 4
        assert count_tokens_approx(msgs) == 12

    def test_assistant_message(self) -> None:
        from pykit_llm.types import TextBlock

        msgs: list[Message] = [AssistantMessage(content=[TextBlock(text="response text")])]
        # 13 // 4 + 4 message framing tokens
        assert count_tokens_approx(msgs) == 7
