"""Universal LLM types mirroring gokit/llm/types.go."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class Role(enum.StrEnum):
    """Message role in a conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """A single message in a conversation."""

    role: Role
    content: str
    name: str | None = None


@dataclass
class Usage:
    """Token usage statistics."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class CompletionRequest:
    """Universal completion request sent to any LLM provider."""

    messages: list[Message]
    model: str = ""
    temperature: float = 0.7
    max_tokens: int | None = None
    stream: bool = False
    stop: list[str] | None = None
    extra: dict[str, object] = field(default_factory=dict)


@dataclass
class CompletionResponse:
    """Universal completion response from any LLM provider."""

    content: str
    model: str = ""
    usage: Usage | None = None
    finish_reason: str = "stop"


@dataclass
class StreamChunk:
    """A single chunk from a streaming completion."""

    content: str = ""
    done: bool = False
    usage: Usage | None = None
