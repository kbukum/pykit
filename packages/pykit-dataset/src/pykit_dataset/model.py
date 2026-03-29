"""Core data types for the dataset module."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, StrEnum


class MediaType(StrEnum):
    """Supported media types."""

    IMAGE = "image"
    TEXT = "text"
    AUDIO = "audio"
    VIDEO = "video"


class Label(IntEnum):
    """Binary classification label."""

    REAL = 0
    AI_GENERATED = 1


@dataclass(frozen=True, slots=True)
class DataItem:
    """A single data sample flowing through the pipeline.

    Carries raw bytes so sources don't need filesystem access.
    The collector handles persistence.
    """

    content: bytes
    label: Label
    media_type: MediaType
    source_name: str
    extension: str = ".jpg"
    metadata: dict[str, str] = field(default_factory=dict)
