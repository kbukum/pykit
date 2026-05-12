"""Universal LLM types built on canonical pykit_ai messages."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict

from pykit_ai import (
    AssistantMessage,
    ContentBlock,
    ContentPart,
    FileBlock,
    FinishReason,
    ImageBlock,
    Message,
    Model,
    SystemMessage,
    TextBlock,
    ToolResultBlock,
    ToolResultMessage,
    ToolUseBlock,
    Usage,
    UserMessage,
    assistant,
    system,
    text_content,
    text_of,
    tool_result_msg,
    user,
)
from pykit_tool import Definition

ThinkingBlock = TextBlock


class _StreamToolCall(BaseModel):
    """Internal streaming accumulation buffer. Not part of the public API."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int = 0
    id: str = ""
    name: str = ""
    input_delta: str = ""


@dataclass
class ToolChoice:
    """Tool selection policy used by compatibility request types."""

    mode: str = "auto"
    function: str | None = None

    @classmethod
    def auto(cls) -> ToolChoice:
        return cls(mode="auto")

    @classmethod
    def none(cls) -> ToolChoice:
        return cls(mode="none")

    @classmethod
    def required(cls) -> ToolChoice:
        return cls(mode="required")

    @classmethod
    def specific(cls, name: str) -> ToolChoice:
        return cls(mode="specific", function=name)


@dataclass
class CompletionRequest:
    """Internal LLM completion request. Consumers should use pykit_ai types at boundaries."""

    messages: list[Message]
    model: str = ""
    temperature: float = 0.7
    max_tokens: int | None = None
    stream: bool = False
    stop: list[str] | None = None
    tools: list[Definition] | None = None
    tool_choice: ToolChoice | None = None
    extra: dict[str, object] = field(default_factory=dict)


@dataclass
class CompletionResponse:
    """Internal LLM completion response. Consumers should use pykit_ai messages at boundaries."""

    message: AssistantMessage
    model: str = ""
    usage: Usage = field(default_factory=Usage)
    stop_reason: FinishReason = FinishReason.STOP

    def has_tool_calls(self) -> bool:
        """Return True if the response contains tool call requests."""
        return self.message.has_tool_calls()

    def text(self) -> str:
        """Extract concatenated text from the assistant message."""
        return self.message.text()


@dataclass
class StreamChunk:
    """Legacy streaming chunk used by compatibility providers and tests."""

    content: str = ""
    done: bool = False
    usage: Usage | None = None
    tool_calls: list[_StreamToolCall] | None = None


__all__ = [
    "AssistantMessage",
    "CompletionRequest",
    "CompletionResponse",
    "ContentBlock",
    "ContentPart",
    "FileBlock",
    "ImageBlock",
    "Message",
    "Model",
    "StreamChunk",
    "SystemMessage",
    "TextBlock",
    "ThinkingBlock",
    "ToolChoice",
    "ToolResultBlock",
    "ToolResultMessage",
    "ToolUseBlock",
    "Usage",
    "UserMessage",
    "assistant",
    "system",
    "text_content",
    "text_of",
    "tool_result_msg",
    "user",
]
