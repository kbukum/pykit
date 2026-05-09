"""Embedding data types, distance metrics, and aggregation functions."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pykit_ai import Model, Usage


class Text(BaseModel):
    """Text embedding input."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["text"] = "text"
    text: str


class Image(BaseModel):
    """Image embedding input from bytes or URL."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["image"] = "image"
    data: bytes | None = None
    url: str | None = None

    @model_validator(mode="after")
    def _has_source(self) -> Image:
        if self.data is None and self.url is None:
            raise ValueError("image input requires data or url")
        return self


class Audio(BaseModel):
    """Audio embedding input from bytes or URL."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["audio"] = "audio"
    data: bytes | None = None
    url: str | None = None

    @model_validator(mode="after")
    def _has_source(self) -> Audio:
        if self.data is None and self.url is None:
            raise ValueError("audio input requires data or url")
        return self


class Video(BaseModel):
    """Video embedding input from bytes or URL."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["video"] = "video"
    data: bytes | None = None
    url: str | None = None

    @model_validator(mode="after")
    def _has_source(self) -> Video:
        if self.data is None and self.url is None:
            raise ValueError("video input requires data or url")
        return self


EmbedInput = Annotated[Text | Image | Audio | Video, Field(discriminator="type")]


class Embedding(BaseModel):
    """A single embedding vector and source input index."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    vector: list[float]
    dimensions: int
    index: int

    @model_validator(mode="after")
    def _dimensions_match(self) -> Embedding:
        if self.dimensions != len(self.vector):
            raise ValueError("embedding dimensions must match vector length")
        return self


class EmbedRequest(BaseModel):
    """Canonical embedding request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: Model
    inputs: list[EmbedInput]
    options: dict[str, Any] = Field(default_factory=dict)


class EmbedResponse(BaseModel):
    """Canonical embedding response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    embeddings: list[Embedding]
    model: Model
    usage: Usage = Field(default_factory=Usage)
