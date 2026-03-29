"""Video format detection from raw bytes."""

from pykit_media.types import MediaInfo, MediaType

# ftyp brands that are image formats (handled by image detector)
_IMAGE_FTYP_BRANDS = frozenset({b"avif", b"avis", b"heic", b"heix", b"heif"})

# ftyp brands mapping to MP4
_MP4_BRANDS = frozenset({b"isom", b"iso2", b"mp41", b"mp42", b"avc1", b"dash"})


def detect_video(data: bytes) -> tuple[MediaInfo, bool]:
    """Detect video format from raw bytes.

    Returns (MediaInfo, True) if a video format is detected, or
    (MediaInfo, False) if no video format is recognized.
    May also return audio info for M4A/M4B ftyp brands.
    """
    if len(data) < 4:
        return MediaInfo(), False

    # ftyp box detection (MP4/MOV/M4V and audio variants)
    if len(data) >= 8 and data[4:8] == b"ftyp":
        return _detect_ftyp(data)

    # EBML header (WebM/MKV): 0x1A45DFA3
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return _detect_ebml(data)

    # RIFF/AVI: "RIFF" + 4 size bytes + "AVI "
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"AVI ":
        return (
            MediaInfo(
                type=MediaType.VIDEO,
                format="avi",
                mime_type="video/x-msvideo",
                container="avi",
            ),
            True,
        )

    # FLV
    if data[:3] == b"FLV":
        return (
            MediaInfo(
                type=MediaType.VIDEO,
                format="flv",
                mime_type="video/x-flv",
                container="flv",
            ),
            True,
        )

    # MPEG-TS: sync byte 0x47 at offset 0 and 188
    if len(data) >= 189 and data[0] == 0x47 and data[188] == 0x47:
        return (
            MediaInfo(
                type=MediaType.VIDEO,
                format="ts",
                mime_type="video/mp2t",
                container="mpegts",
            ),
            True,
        )

    return MediaInfo(), False


def _detect_ftyp(data: bytes) -> tuple[MediaInfo, bool]:
    """Detect format from ftyp box brand."""
    if len(data) < 12:
        return MediaInfo(), False

    brand = data[8:12]

    # Skip image brands — let image detector handle them
    if brand in _IMAGE_FTYP_BRANDS:
        return MediaInfo(), False

    # QuickTime MOV
    if brand == b"qt  ":
        return (
            MediaInfo(
                type=MediaType.VIDEO,
                format="mov",
                mime_type="video/quicktime",
                container="mov",
            ),
            True,
        )

    # M4V variants
    if brand in (b"M4V ", b"M4VH", b"M4VP"):
        return (
            MediaInfo(
                type=MediaType.VIDEO,
                format="m4v",
                mime_type="video/x-m4v",
                container="mp4",
            ),
            True,
        )

    # M4A / M4B — audio in MP4 container
    if brand in (b"M4A ", b"M4B "):
        return (
            MediaInfo(
                type=MediaType.AUDIO,
                format="m4a",
                mime_type="audio/mp4",
                container="mp4",
            ),
            True,
        )

    # Standard MP4 brands or unknown ftyp → default to MP4
    return (
        MediaInfo(
            type=MediaType.VIDEO,
            format="mp4",
            mime_type="video/mp4",
            container="mp4",
        ),
        True,
    )


def _detect_ebml(data: bytes) -> tuple[MediaInfo, bool]:
    """Detect WebM vs MKV from EBML header."""
    # Search for "webm" in the header region
    search_limit = min(len(data), 64)
    if b"webm" in data[:search_limit]:
        return (
            MediaInfo(
                type=MediaType.VIDEO,
                format="webm",
                mime_type="video/webm",
                container="webm",
            ),
            True,
        )

    return (
        MediaInfo(
            type=MediaType.VIDEO,
            format="mkv",
            mime_type="video/x-matroska",
            container="mkv",
        ),
        True,
    )
