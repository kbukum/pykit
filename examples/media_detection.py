"""Example: Media type detection from raw bytes.

Demonstrates:
- Detecting JPEG, PNG, MP3, MP4, and plain text from byte headers
- Using detect() for in-memory buffers
- Using is_text() for the text heuristic
"""

from __future__ import annotations

from pykit_media import MediaType, detect, is_text


def make_sample_headers() -> list[tuple[str, bytes]]:
    """Return (label, header_bytes) pairs for common media formats."""
    return [
        # JPEG: starts with FF D8 FF
        ("JPEG image", b"\xff\xd8\xff\xe0" + b"\x00" * 20),
        # PNG: starts with 89 50 4E 47 0D 0A 1A 0A
        ("PNG image", b"\x89PNG\r\n\x1a\n" + b"\x00" * 20),
        # MP3: ID3 tag header
        ("MP3 audio", b"ID3" + b"\x04\x00\x00" + b"\x00" * 20),
        # MP4: ftyp box
        ("MP4 video", b"\x00\x00\x00\x1c" + b"ftypisom" + b"\x00" * 20),
        # Plain text (UTF-8)
        ("Plain text", b"Hello, world! This is a plain text document.\n"),
        # Unknown binary
        ("Unknown binary", b"\x00\x01\x02\x03\x80\x81\x82\x83"),
    ]


def demo_detect() -> None:
    """Detect media types from byte headers."""
    print("=== Media Detection ===\n")
    print(f"  {'Label':<16} {'Type':<10} {'Format':<8} {'MIME'}")
    print(f"  {'─' * 16} {'─' * 10} {'─' * 8} {'─' * 24}")

    for label, data in make_sample_headers():
        info = detect(data)
        print(f"  {label:<16} {info.type.value:<10} {info.format or '—':<8} {info.mime_type or '—'}")


def demo_is_text() -> None:
    """Show the text heuristic on various inputs."""
    print("\n=== Text Heuristic ===\n")
    samples = [
        ("UTF-8 prose", b"The quick brown fox jumps over the lazy dog."),
        ("JSON", b'{"key": "value", "numbers": [1, 2, 3]}'),
        ("Binary blob", bytes(range(256))),
        ("Empty", b""),
    ]

    for label, data in samples:
        result = is_text(data)
        print(f"  {label:<16} → is_text={result}")


def demo_type_enum() -> None:
    """Enumerate all MediaType values."""
    print("\n=== MediaType Enum ===\n")
    for mt in MediaType:
        print(f"  {mt.name} = {mt.value!r}")


if __name__ == "__main__":
    demo_detect()
    demo_is_text()
    demo_type_enum()
