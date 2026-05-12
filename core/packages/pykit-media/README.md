# pykit-media

Zero-dependency media type detection from raw bytes using magic byte signatures for video, audio, image, and text formats.

## Installation

```bash
pip install pykit-media
# or
uv add pykit-media
```

## Quick Start

```python
from pathlib import Path
from pykit_media import detect, detect_file, MediaType, is_text

# Detect from bytes (reads first 4096 bytes)
with open("photo.jpg", "rb") as f:
    info = detect(f.read())

print(info.type)       # MediaType.IMAGE
print(info.format)     # "jpeg"
print(info.mime_type)  # "image/jpeg"

# Detect from file path
info = detect_file(Path("video.mp4"))
print(info.type)       # MediaType.VIDEO
print(info.container)  # "mp4"

# Check for text content
assert is_text(b"Hello, world!")
```

## Key Components

- **detect(data)** — Detect media type from raw bytes; tries detectors in priority order: video → audio → image → text
- **detect_file(path)** — Detect media type from a file path (reads first 4096 bytes)
- **is_text(data)** — Returns `True` if data is valid UTF-8 with ≥95% printable characters
- **MediaInfo** — Frozen dataclass: `type` (MediaType), `format` (e.g., "mp4"), `mime_type` (e.g., "video/mp4"), `container` (e.g., "riff")
- **MediaType** — StrEnum: `UNKNOWN`, `VIDEO`, `AUDIO`, `IMAGE`, `TEXT`

### Supported Formats

| Category | Formats |
|----------|---------|
| **Video** | MP4, MOV, M4V, WebM, MKV, AVI, FLV, MPEG-TS |
| **Audio** | WAV, FLAC, OGG, AAC, MP3, MIDI, AIFF, M4A/M4B |
| **Image** | JPEG, PNG, GIF, WebP, BMP, TIFF, ICO, AVIF, HEIF |
| **Text** | UTF-8 with printable character ratio ≥95% |

## Dependencies

None — pure Python implementation using only the standard library.

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
