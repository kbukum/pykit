"""Audio format detection from raw bytes."""

from pykit_media.types import MediaInfo, MediaType


def detect_audio(data: bytes) -> tuple[MediaInfo, bool]:
    """Detect audio format from raw bytes.

    Returns (MediaInfo, True) if an audio format is detected, or
    (MediaInfo, False) if no audio format is recognized.
    """
    if len(data) < 4:
        return MediaInfo(), False

    # WAV: "RIFF" + 4 size bytes + "WAVE"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return (
            MediaInfo(
                type=MediaType.AUDIO,
                format="wav",
                mime_type="audio/wav",
                container="riff",
            ),
            True,
        )

    # FLAC: "fLaC"
    if data[:4] == b"fLaC":
        return (
            MediaInfo(
                type=MediaType.AUDIO,
                format="flac",
                mime_type="audio/flac",
                container="flac",
            ),
            True,
        )

    # OGG: "OggS"
    if data[:4] == b"OggS":
        return (
            MediaInfo(
                type=MediaType.AUDIO,
                format="ogg",
                mime_type="audio/ogg",
                container="ogg",
            ),
            True,
        )

    # AAC: ADTS sync word (0xFFF0 or 0xFFF1 — top 12 bits = 0xFFF)
    # Must check before MP3 since frame syncs overlap
    if len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xF0) == 0xF0:
        # ADTS frame: bits 12 = ID, bit 13-14 = layer (must be 00 for AAC)
        layer = (data[1] >> 1) & 0x03
        if layer == 0:
            return (
                MediaInfo(
                    type=MediaType.AUDIO,
                    format="aac",
                    mime_type="audio/aac",
                    container="adts",
                ),
                True,
            )

    # MP3: ID3 tag
    if data[:3] == b"ID3":
        return (
            MediaInfo(
                type=MediaType.AUDIO,
                format="mp3",
                mime_type="audio/mpeg",
                container="mp3",
            ),
            True,
        )

    # MP3: frame sync (0xFF + top 3 bits of next byte set = 0xFFE0)
    if len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        # Ensure layer is not 00 (that's AAC/reserved, already handled above)
        layer = (data[1] >> 1) & 0x03
        if layer != 0:
            return (
                MediaInfo(
                    type=MediaType.AUDIO,
                    format="mp3",
                    mime_type="audio/mpeg",
                    container="mp3",
                ),
                True,
            )

    # MIDI: "MThd"
    if data[:4] == b"MThd":
        return (
            MediaInfo(
                type=MediaType.AUDIO,
                format="midi",
                mime_type="audio/midi",
                container="midi",
            ),
            True,
        )

    # AIFF: "FORM" + 4 size bytes + "AIFF"
    if len(data) >= 12 and data[:4] == b"FORM" and data[8:12] == b"AIFF":
        return (
            MediaInfo(
                type=MediaType.AUDIO,
                format="aiff",
                mime_type="audio/aiff",
                container="aiff",
            ),
            True,
        )

    return MediaInfo(), False
