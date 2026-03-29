"""pykit-media — Detect media types from raw bytes using magic byte signatures."""

__version__ = "0.1.0"

from pykit_media.detect import detect, detect_file, is_text
from pykit_media.types import MediaInfo, MediaType

__all__ = [
    "MediaInfo",
    "MediaType",
    "detect",
    "detect_file",
    "is_text",
]
