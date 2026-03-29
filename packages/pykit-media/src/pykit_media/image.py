"""Image format detection from raw bytes."""

from pykit_media.types import MediaInfo, MediaType

# ftyp brands for AVIF
_AVIF_BRANDS = frozenset({b"avif", b"avis"})

# ftyp brands for HEIF
_HEIF_BRANDS = frozenset({b"heic", b"heix", b"heif"})


def detect_image(data: bytes) -> tuple[MediaInfo, bool]:
    """Detect image format from raw bytes.

    Returns (MediaInfo, True) if an image format is detected, or
    (MediaInfo, False) if no image format is recognized.
    """
    if len(data) < 2:
        return MediaInfo(), False

    # JPEG: FF D8 FF
    if len(data) >= 3 and data[0] == 0xFF and data[1] == 0xD8 and data[2] == 0xFF:
        return (
            MediaInfo(
                type=MediaType.IMAGE,
                format="jpeg",
                mime_type="image/jpeg",
                container="jpeg",
            ),
            True,
        )

    # PNG: 89 50 4E 47 0D 0A 1A 0A
    if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return (
            MediaInfo(
                type=MediaType.IMAGE,
                format="png",
                mime_type="image/png",
                container="png",
            ),
            True,
        )

    # GIF: "GIF87a" or "GIF89a"
    if len(data) >= 6 and (data[:6] == b"GIF87a" or data[:6] == b"GIF89a"):
        return (
            MediaInfo(
                type=MediaType.IMAGE,
                format="gif",
                mime_type="image/gif",
                container="gif",
            ),
            True,
        )

    # WebP: "RIFF" + 4 size bytes + "WEBP"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return (
            MediaInfo(
                type=MediaType.IMAGE,
                format="webp",
                mime_type="image/webp",
                container="riff",
            ),
            True,
        )

    # BMP: "BM"
    if data[:2] == b"BM":
        return (
            MediaInfo(
                type=MediaType.IMAGE,
                format="bmp",
                mime_type="image/bmp",
                container="bmp",
            ),
            True,
        )

    # TIFF: Little-endian "II" + 0x2A00 or Big-endian "MM" + 0x002A
    if len(data) >= 4:
        if data[:2] == b"II" and data[2] == 0x2A and data[3] == 0x00:
            return (
                MediaInfo(
                    type=MediaType.IMAGE,
                    format="tiff",
                    mime_type="image/tiff",
                    container="tiff",
                ),
                True,
            )
        if data[:2] == b"MM" and data[2] == 0x00 and data[3] == 0x2A:
            return (
                MediaInfo(
                    type=MediaType.IMAGE,
                    format="tiff",
                    mime_type="image/tiff",
                    container="tiff",
                ),
                True,
            )

    # ICO: 00 00 01 00
    if len(data) >= 4 and data[:4] == b"\x00\x00\x01\x00":
        return (
            MediaInfo(
                type=MediaType.IMAGE,
                format="ico",
                mime_type="image/x-icon",
                container="ico",
            ),
            True,
        )

    # AVIF / HEIF: ftyp box with image brands
    if len(data) >= 12 and data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in _AVIF_BRANDS:
            return (
                MediaInfo(
                    type=MediaType.IMAGE,
                    format="avif",
                    mime_type="image/avif",
                    container="mp4",
                ),
                True,
            )
        if brand in _HEIF_BRANDS:
            return (
                MediaInfo(
                    type=MediaType.IMAGE,
                    format="heif",
                    mime_type="image/heif",
                    container="mp4",
                ),
                True,
            )

    return MediaInfo(), False
