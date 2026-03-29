"""Media type definitions."""

from dataclasses import dataclass
from enum import Enum


class MediaType(Enum):
    """Supported media type categories."""

    UNKNOWN = "unknown"
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    TEXT = "text"


@dataclass(frozen=True)
class MediaInfo:
    """Detection result containing media type, format, MIME type, and container."""

    type: MediaType = MediaType.UNKNOWN
    format: str = ""
    mime_type: str = ""
    container: str = ""
