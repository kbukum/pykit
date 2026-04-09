"""StreamEvent — discriminated union for streaming completion events."""

from __future__ import annotations

from dataclasses import dataclass

from pykit_llm.types import CompletionResponse, Usage


@dataclass
class ContentDelta:
    """A chunk of text content from the stream."""

    text: str
    type: str = "content_delta"


@dataclass
class ToolCallDelta:
    """A chunk of a tool call being streamed."""

    tool_use_id: str
    name: str | None
    arguments_chunk: str
    type: str = "tool_call_delta"


@dataclass
class ThinkingDelta:
    """A chunk of thinking/reasoning content."""

    text: str
    type: str = "thinking_delta"


@dataclass
class UsageUpdate:
    """Token usage statistics update."""

    usage: Usage
    type: str = "usage_update"


@dataclass
class MessageStart:
    """Marks the beginning of a new message."""

    model: str
    role: str
    type: str = "message_start"


@dataclass
class MessageComplete:
    """The final assembled response."""

    response: CompletionResponse
    type: str = "message_complete"


@dataclass
class StreamError:
    """An error that occurred during streaming."""

    error: str
    code: str | None = None
    type: str = "stream_error"


StreamEvent = (
    ContentDelta
    | ToolCallDelta
    | ThinkingDelta
    | UsageUpdate
    | MessageStart
    | MessageComplete
    | StreamError
)
