"""Canonical AI message types — role-discriminated message union."""

from __future__ import annotations

from typing import Annotated, Literal, TypeAliasType

from pydantic import BaseModel, ConfigDict, Field

from pykit_ai.content import ContentPart, Text, ToolUseBlock
from pykit_ai.core import Role, Usage


class UserMessage(BaseModel):
    """Canonical user-authored chat message."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Literal[Role.USER] = Role.USER
    content: list[ContentPart]

    @classmethod
    def from_text(cls, text: str) -> UserMessage:
        return cls(content=[Text(text=text)])


class AssistantMessage(BaseModel):
    """Canonical assistant chat message with optional tool-use blocks."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Literal[Role.ASSISTANT] = Role.ASSISTANT
    content: list[ContentPart] = Field(default_factory=list)
    tool_calls: list[ToolUseBlock] = Field(default_factory=list)
    usage: Usage | None = None

    def text(self) -> str:
        return "".join(part.text for part in self.content if hasattr(part, "text"))

    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


class SystemMessage(BaseModel):
    """Canonical system instruction message."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Literal[Role.SYSTEM] = Role.SYSTEM
    content: str


class ToolResultMessage(BaseModel):
    """Canonical tool-result message returned to the model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Literal[Role.TOOL] = Role.TOOL
    tool_use_id: str
    content: str
    is_error: bool = False


Message = TypeAliasType(  # noqa: UP040
    "Message",
    Annotated[
        UserMessage | AssistantMessage | SystemMessage | ToolResultMessage,
        Field(discriminator="role"),
    ],
)


def user(text: str) -> UserMessage:
    """Create a user message from plain text."""
    return UserMessage.from_text(text)


def assistant(text: str) -> AssistantMessage:
    """Create an assistant message from plain text."""
    return AssistantMessage(content=[Text(text=text)])


def system(text: str) -> SystemMessage:
    """Create a system message."""
    return SystemMessage(content=text)


def tool_result_msg(tool_use_id: str, content: str, is_error: bool = False) -> ToolResultMessage:
    """Create a tool result message."""
    return ToolResultMessage(tool_use_id=tool_use_id, content=content, is_error=is_error)


def text_content(text: str) -> list[ContentPart]:
    """Create a single-element text content list."""
    return [Text(text=text)]


def text_of(blocks: list[ContentPart]) -> str:
    """Extract concatenated text from content blocks."""
    return "".join(block.text for block in blocks if hasattr(block, "text"))


def count_tokens_approx(messages: list[Message]) -> int:
    """Estimate token count using the 4-chars≈1-token heuristic."""
    total = 0
    for message in messages:
        if isinstance(message, UserMessage):
            text = text_of(message.content)
            total += len(text) // 4 + 4
        elif isinstance(message, AssistantMessage):
            total += len(message.text()) // 4 + len(message.tool_calls) + 4
        elif isinstance(message, (SystemMessage, ToolResultMessage)):
            total += len(message.content) // 4 + 4
    return total


__all__ = [
    "AssistantMessage",
    "Message",
    "SystemMessage",
    "ToolResultMessage",
    "UserMessage",
    "assistant",
    "count_tokens_approx",
    "system",
    "text_content",
    "text_of",
    "tool_result_msg",
    "user",
]
