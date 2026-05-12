"""Canonical AI content block vocabulary."""

from __future__ import annotations

from typing import Annotated, Literal, TypeAliasType

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class Text(BaseModel):
    """Text content part."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["text"] = "text"
    text: str


class Image(BaseModel):
    """Image content part."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["image"] = "image"
    source: str
    mime_type: str
    data: str = ""


class Audio(BaseModel):
    """Audio content part."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["audio"] = "audio"
    source: str
    mime_type: str
    data: str = ""


class Video(BaseModel):
    """Video content part."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["video"] = "video"
    source: str
    mime_type: str
    data: str = ""


class File(BaseModel):
    """File content part."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["file"] = "file"
    source: str
    mime_type: str = "application/octet-stream"
    filename: str = ""
    data: str = ""


class ToolUseBlock(BaseModel):
    """Tool invocation request block emitted by a model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["tool_use"] = "tool_use"
    id: str = ""
    name: str
    input: dict[str, JsonValue] = Field(default_factory=dict)


class ToolResultBlock(BaseModel):
    """Tool execution result block fed back to a model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["tool_result"] = "tool_result"
    id: str = ""
    content: list[JsonValue] = Field(default_factory=list)
    is_error: bool = False


ContentPart = TypeAliasType(  # noqa: UP040
    "ContentPart",
    Annotated[
        Text | Image | Audio | Video | File | ToolUseBlock | ToolResultBlock,
        Field(discriminator="type"),
    ],
)

TextBlock = Text
ImageBlock = Image
AudioBlock = Audio
VideoBlock = Video
FileBlock = File
ContentBlock = ContentPart

__all__ = [
    "Audio",
    "AudioBlock",
    "ContentBlock",
    "ContentPart",
    "File",
    "FileBlock",
    "Image",
    "ImageBlock",
    "JsonValue",
    "Text",
    "TextBlock",
    "ToolResultBlock",
    "ToolUseBlock",
    "Video",
    "VideoBlock",
]
