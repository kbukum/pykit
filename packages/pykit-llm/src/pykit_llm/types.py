"""Universal LLM types — discriminated union message types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pykit_tool import Definition

# --- Content Blocks ---


@dataclass
class TextBlock:
    """A block of text content."""

    text: str


@dataclass
class ImageBlock:
    """An image content block."""

    source: str
    mime_type: str
    data: str = ""


@dataclass
class ToolUseBlock:
    """A tool invocation request from the LLM."""

    id: str
    name: str
    input: dict[str, Any]


@dataclass
class ToolResultBlock:
    """A tool execution result fed back to the LLM."""

    tool_use_id: str
    content: str
    is_error: bool = False


@dataclass
class ThinkingBlock:
    """A thinking/reasoning block from the LLM."""

    text: str


ContentBlock = TextBlock | ImageBlock | ToolUseBlock | ToolResultBlock | ThinkingBlock


# --- Messages ---


@dataclass
class UserMessage:
    """A message from the user."""

    content: list[ContentBlock]

    @property
    def role(self) -> str:
        return "user"


@dataclass
class AssistantMessage:
    """A message from the assistant."""

    content: list[ContentBlock] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage | None = None

    @property
    def role(self) -> str:
        return "assistant"


@dataclass
class ToolResultMessage:
    """A tool result message."""

    tool_use_id: str
    content: str
    is_error: bool = False

    @property
    def role(self) -> str:
        return "tool_result"


@dataclass
class SystemMessage:
    """A system message."""

    content: str

    @property
    def role(self) -> str:
        return "system"


Message = UserMessage | AssistantMessage | ToolResultMessage | SystemMessage


# --- Convenience constructors ---


def user(text: str) -> UserMessage:
    """Create a user message from plain text."""
    return UserMessage(content=[TextBlock(text=text)])


def assistant(text: str) -> AssistantMessage:
    """Create an assistant message from plain text."""
    return AssistantMessage(content=[TextBlock(text=text)])


def system(text: str) -> SystemMessage:
    """Create a system message."""
    return SystemMessage(content=text)


def tool_result_msg(tool_use_id: str, content: str, is_error: bool = False) -> ToolResultMessage:
    """Create a tool result message."""
    return ToolResultMessage(tool_use_id=tool_use_id, content=content, is_error=is_error)


def text_content(text: str) -> list[ContentBlock]:
    """Create a single-element text content list."""
    return [TextBlock(text=text)]


def text_of(blocks: list[ContentBlock]) -> str:
    """Extract concatenated text from content blocks."""
    return "".join(b.text for b in blocks if isinstance(b, TextBlock))


# --- Stop Reason ---


class StopReason:
    """Constants for completion stop reasons."""

    END_TURN = "end_turn"
    TOOL_USE = "tool_use"
    MAX_TOKENS = "max_tokens"
    CONTENT_FILTER = "content_filter"
    STOP_SEQUENCE = "stop_sequence"


# --- Tool calling types ---


@dataclass
class FunctionCall:
    """Function invocation details within a tool call."""

    name: str
    arguments: str  # JSON string of function arguments


@dataclass
class ToolCall:
    """An LLM's request to invoke a tool."""

    id: str
    function: FunctionCall
    type: str = "function"


@dataclass
class ToolChoice:
    """Controls how the model selects tools.

    Modes:
        - ``"auto"``: model decides whether to call tools (default)
        - ``"none"``: model must not call any tools
        - ``"required"``: model must call at least one tool
        - ``"specific"``: model must call the named tool
    """

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
class Usage:
    """Token usage statistics."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


# --- Request / Response ---


@dataclass
class CompletionRequest:
    """Universal completion request sent to any LLM provider."""

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
    """Universal completion response from any LLM provider."""

    message: AssistantMessage
    model: str = ""
    usage: Usage = field(default_factory=Usage)
    stop_reason: str = ""

    def has_tool_calls(self) -> bool:
        """Return True if the response contains tool call requests."""
        return len(self.message.tool_calls) > 0

    def text(self) -> str:
        """Extract concatenated text from the assistant message."""
        return text_of(self.message.content)


@dataclass
class StreamChunk:
    """A single chunk from a streaming completion."""

    content: str = ""
    done: bool = False
    usage: Usage | None = None
    tool_calls: list[ToolCall] | None = None
