"""Canonical AI streaming event types."""

from __future__ import annotations

from typing import Annotated, Literal, Protocol, TypeAliasType, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from pykit_ai.content import ToolUseBlock
from pykit_ai.core import FinishReason, Usage


class MessageStart(BaseModel):
    """Marker that a streamed message has begun."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["message.start"] = "message.start"
    model: str = ""
    role: str = "assistant"

    def _stream_event_marker(self) -> None:
        return None


class MessageStop(BaseModel):
    """Terminal marker for a streamed message."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["message.stop"] = "message.stop"
    finish_reason: FinishReason | None = None
    response: object | None = None

    def _stream_event_marker(self) -> None:
        return None


class ToolUseStart(BaseModel):
    """Beginning of a streamed tool-use block."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["tool_use.start"] = "tool_use.start"
    id: str
    name: str

    def _stream_event_marker(self) -> None:
        return None


class ToolUseDelta(BaseModel):
    """Incremental input fragment for an in-flight tool-use block."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["tool_use.delta"] = "tool_use.delta"
    id: str
    input_delta: str

    def _stream_event_marker(self) -> None:
        return None


class ToolUseStop(BaseModel):
    """Terminal marker for a streamed tool-use block."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["tool_use.stop"] = "tool_use.stop"
    id: str
    block: ToolUseBlock | None = None

    def _stream_event_marker(self) -> None:
        return None


@runtime_checkable
class StreamEvent(Protocol):
    """Universal stream event protocol.

    All concrete stream event models expose a ``type`` discriminator and a marker
    method so chat-specific and non-chat events can be typed structurally.
    """

    @property
    def type(self) -> str:
        """Discriminator field identifying the event variant."""

    def _stream_event_marker(self) -> None:
        """Mark this object as a structural stream event."""


class TextDelta(BaseModel):
    """Incremental assistant text emitted during streaming."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["text.delta"] = "text.delta"
    text: str

    def _stream_event_marker(self) -> None:
        """Mark this model as a structural stream event."""
        return None


class ReasoningDelta(BaseModel):
    """Incremental reasoning text emitted during streaming."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["reasoning.delta"] = "reasoning.delta"
    text: str

    def _stream_event_marker(self) -> None:
        """Mark this model as a structural stream event."""
        return None


class UsageDelta(BaseModel):
    """Incremental usage accounting emitted during streaming."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["usage.delta"] = "usage.delta"
    usage: Usage
    cached_tokens: int | None = None

    def _stream_event_marker(self) -> None:
        """Mark this model as a structural stream event."""
        return None


class StreamError(BaseModel):
    """Terminal streaming error event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["stream.error"] = "stream.error"
    error: str
    code: str | None = None

    def _stream_event_marker(self) -> None:
        """Mark this model as a structural stream event."""
        return None


Error = StreamError

AnyStreamEvent = TypeAliasType(  # noqa: UP040
    "AnyStreamEvent",
    Annotated[
        MessageStart
        | TextDelta
        | ReasoningDelta
        | ToolUseStart
        | ToolUseDelta
        | ToolUseStop
        | MessageStop
        | UsageDelta
        | StreamError,
        Field(discriminator="type"),
    ],
)

__all__ = [
    "AnyStreamEvent",
    "Error",
    "MessageStart",
    "MessageStop",
    "ReasoningDelta",
    "StreamError",
    "StreamEvent",
    "TextDelta",
    "ToolUseDelta",
    "ToolUseStart",
    "ToolUseStop",
    "UsageDelta",
]
