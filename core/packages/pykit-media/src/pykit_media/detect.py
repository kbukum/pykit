"""Main media detection entry point."""

from pathlib import Path

from pykit_media.audio import detect_audio
from pykit_media.image import detect_image
from pykit_media.types import MediaInfo, MediaType
from pykit_media.video import detect_video

_MAX_HEADER = 4096


def detect(data: bytes) -> MediaInfo:
    """Detect media type from raw bytes.

    Inspects at most the first 4096 bytes. Tries video, audio, image
    detection in order, then falls back to a text heuristic.
    """
    if not data:
        return MediaInfo()

    header = data[:_MAX_HEADER]

    # Try detectors in priority order
    info, matched = detect_video(header)
    if matched:
        return info

    info, matched = detect_audio(header)
    if matched:
        return info

    info, matched = detect_image(header)
    if matched:
        return info

    # Text heuristic fallback
    if is_text(header):
        return MediaInfo(
            type=MediaType.TEXT,
            format="txt",
            mime_type="text/plain",
            container="",
        )

    return MediaInfo()


def detect_file(path: str | Path) -> MediaInfo:
    """Open a file and detect media type from its first 4096 bytes."""
    p = Path(path)
    with p.open("rb") as f:
        data = f.read(_MAX_HEADER)
    return detect(data)


def is_text(data: bytes) -> bool:
    """Check if data appears to be UTF-8 text.

    Returns True if the data is valid UTF-8 and at least 95% of its
    codepoints are printable or whitespace characters.
    """
    if not data:
        return False

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False

    if not text:
        return False

    total = len(text)
    printable = sum(1 for ch in text if ch.isprintable() or ch in "\t\n\r")
    return (printable / total) >= 0.95
