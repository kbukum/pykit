"""Comprehensive tests for pykit-media detection."""

from pathlib import Path

import pytest

from pykit_media import MediaInfo, MediaType, detect, detect_file, is_text


# ---------------------------------------------------------------------------
# Helper to build ftyp boxes
# ---------------------------------------------------------------------------
def _ftyp(brand: bytes, extra: bytes = b"") -> bytes:
    """Build a minimal ftyp box with the given brand."""
    # Box size (8 header + 4 brand + extra), "ftyp", brand, extra
    size = 8 + 4 + len(extra)
    return size.to_bytes(4, "big") + b"ftyp" + brand + extra


# ===========================================================================
# Video detection
# ===========================================================================
class TestVideoDetection:
    @pytest.mark.parametrize(
        "brand",
        [b"isom", b"iso2", b"mp41", b"mp42", b"avc1", b"dash"],
    )
    def test_mp4_brands(self, brand: bytes) -> None:
        info = detect(_ftyp(brand))
        assert info.type == MediaType.VIDEO
        assert info.format == "mp4"
        assert info.mime_type == "video/mp4"

    def test_mp4_unknown_brand(self) -> None:
        info = detect(_ftyp(b"XXXX"))
        assert info.type == MediaType.VIDEO
        assert info.format == "mp4"

    def test_mov(self) -> None:
        info = detect(_ftyp(b"qt  "))
        assert info.type == MediaType.VIDEO
        assert info.format == "mov"
        assert info.mime_type == "video/quicktime"

    @pytest.mark.parametrize("brand", [b"M4V ", b"M4VH", b"M4VP"])
    def test_m4v(self, brand: bytes) -> None:
        info = detect(_ftyp(brand))
        assert info.type == MediaType.VIDEO
        assert info.format == "m4v"

    def test_webm(self) -> None:
        header = b"\x1a\x45\xdf\xa3" + b"\x00" * 10 + b"webm" + b"\x00" * 20
        info = detect(header)
        assert info.type == MediaType.VIDEO
        assert info.format == "webm"
        assert info.mime_type == "video/webm"

    def test_mkv(self) -> None:
        header = b"\x1a\x45\xdf\xa3" + b"\x00" * 60
        info = detect(header)
        assert info.type == MediaType.VIDEO
        assert info.format == "mkv"
        assert info.mime_type == "video/x-matroska"

    def test_avi(self) -> None:
        data = b"RIFF" + b"\x00" * 4 + b"AVI " + b"\x00" * 100
        info = detect(data)
        assert info.type == MediaType.VIDEO
        assert info.format == "avi"
        assert info.mime_type == "video/x-msvideo"

    def test_flv(self) -> None:
        data = b"FLV\x01\x05" + b"\x00" * 100
        info = detect(data)
        assert info.type == MediaType.VIDEO
        assert info.format == "flv"
        assert info.mime_type == "video/x-flv"

    def test_ts(self) -> None:
        data = b"\x47" + b"\x00" * 187 + b"\x47" + b"\x00" * 100
        info = detect(data)
        assert info.type == MediaType.VIDEO
        assert info.format == "ts"
        assert info.mime_type == "video/mp2t"


# ===========================================================================
# Audio detection (including M4A/M4B via video detector ftyp path)
# ===========================================================================
class TestAudioDetection:
    def test_wav(self) -> None:
        data = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 100
        info = detect(data)
        assert info.type == MediaType.AUDIO
        assert info.format == "wav"
        assert info.mime_type == "audio/wav"

    def test_flac(self) -> None:
        data = b"fLaC" + b"\x00" * 100
        info = detect(data)
        assert info.type == MediaType.AUDIO
        assert info.format == "flac"
        assert info.mime_type == "audio/flac"

    def test_ogg(self) -> None:
        data = b"OggS" + b"\x00" * 100
        info = detect(data)
        assert info.type == MediaType.AUDIO
        assert info.format == "ogg"
        assert info.mime_type == "audio/ogg"

    def test_aac(self) -> None:
        # ADTS sync: 0xFFF1 (MPEG-4, layer=0)
        data = b"\xff\xf1" + b"\x00" * 100
        info = detect(data)
        assert info.type == MediaType.AUDIO
        assert info.format == "aac"
        assert info.mime_type == "audio/aac"

    def test_mp3_id3(self) -> None:
        data = b"ID3\x04\x00" + b"\x00" * 100
        info = detect(data)
        assert info.type == MediaType.AUDIO
        assert info.format == "mp3"
        assert info.mime_type == "audio/mpeg"

    def test_mp3_frame_sync(self) -> None:
        # 0xFFFA = sync + MPEG1 Layer3
        data = b"\xff\xfb" + b"\x00" * 100
        info = detect(data)
        assert info.type == MediaType.AUDIO
        assert info.format == "mp3"
        assert info.mime_type == "audio/mpeg"

    def test_midi(self) -> None:
        data = b"MThd" + b"\x00" * 100
        info = detect(data)
        assert info.type == MediaType.AUDIO
        assert info.format == "midi"
        assert info.mime_type == "audio/midi"

    def test_aiff(self) -> None:
        data = b"FORM" + b"\x00" * 4 + b"AIFF" + b"\x00" * 100
        info = detect(data)
        assert info.type == MediaType.AUDIO
        assert info.format == "aiff"
        assert info.mime_type == "audio/aiff"

    def test_m4a(self) -> None:
        info = detect(_ftyp(b"M4A "))
        assert info.type == MediaType.AUDIO
        assert info.format == "m4a"
        assert info.mime_type == "audio/mp4"

    def test_m4b(self) -> None:
        info = detect(_ftyp(b"M4B "))
        assert info.type == MediaType.AUDIO
        assert info.format == "m4a"


# ===========================================================================
# Image detection
# ===========================================================================
class TestImageDetection:
    def test_jpeg(self) -> None:
        data = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        info = detect(data)
        assert info.type == MediaType.IMAGE
        assert info.format == "jpeg"
        assert info.mime_type == "image/jpeg"

    def test_png(self) -> None:
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        info = detect(data)
        assert info.type == MediaType.IMAGE
        assert info.format == "png"
        assert info.mime_type == "image/png"

    def test_gif87a(self) -> None:
        data = b"GIF87a" + b"\x00" * 100
        info = detect(data)
        assert info.type == MediaType.IMAGE
        assert info.format == "gif"
        assert info.mime_type == "image/gif"

    def test_gif89a(self) -> None:
        data = b"GIF89a" + b"\x00" * 100
        info = detect(data)
        assert info.type == MediaType.IMAGE
        assert info.format == "gif"

    def test_webp(self) -> None:
        data = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 100
        info = detect(data)
        assert info.type == MediaType.IMAGE
        assert info.format == "webp"
        assert info.mime_type == "image/webp"

    def test_bmp(self) -> None:
        data = b"BM" + b"\x00" * 100
        info = detect(data)
        assert info.type == MediaType.IMAGE
        assert info.format == "bmp"
        assert info.mime_type == "image/bmp"

    def test_tiff_le(self) -> None:
        data = b"II\x2a\x00" + b"\x00" * 100
        info = detect(data)
        assert info.type == MediaType.IMAGE
        assert info.format == "tiff"
        assert info.mime_type == "image/tiff"

    def test_tiff_be(self) -> None:
        data = b"MM\x00\x2a" + b"\x00" * 100
        info = detect(data)
        assert info.type == MediaType.IMAGE
        assert info.format == "tiff"
        assert info.mime_type == "image/tiff"

    def test_ico(self) -> None:
        data = b"\x00\x00\x01\x00" + b"\x00" * 100
        info = detect(data)
        assert info.type == MediaType.IMAGE
        assert info.format == "ico"
        assert info.mime_type == "image/x-icon"

    @pytest.mark.parametrize("brand", [b"avif", b"avis"])
    def test_avif(self, brand: bytes) -> None:
        info = detect(_ftyp(brand))
        assert info.type == MediaType.IMAGE
        assert info.format == "avif"
        assert info.mime_type == "image/avif"

    @pytest.mark.parametrize("brand", [b"heic", b"heix", b"heif"])
    def test_heif(self, brand: bytes) -> None:
        info = detect(_ftyp(brand))
        assert info.type == MediaType.IMAGE
        assert info.format == "heif"
        assert info.mime_type == "image/heif"


# ===========================================================================
# Text and unknown detection
# ===========================================================================
class TestTextDetection:
    def test_utf8_text(self) -> None:
        data = b"Hello, world! This is plain text.\n"
        info = detect(data)
        assert info.type == MediaType.TEXT
        assert info.format == "txt"
        assert info.mime_type == "text/plain"

    def test_utf8_with_unicode(self) -> None:
        data = "Héllo wörld 日本語\n".encode()
        info = detect(data)
        assert info.type == MediaType.TEXT

    def test_is_text_true(self) -> None:
        assert is_text(b"Hello world\n") is True

    def test_is_text_false_binary(self) -> None:
        data = bytes(range(256))
        assert is_text(data) is False

    def test_is_text_empty(self) -> None:
        assert is_text(b"") is False


class TestUnknownDetection:
    def test_empty_data(self) -> None:
        info = detect(b"")
        assert info.type == MediaType.UNKNOWN
        assert info.format == ""

    def test_binary_garbage(self) -> None:
        data = bytes(range(256)) * 4
        info = detect(data)
        assert info.type == MediaType.UNKNOWN

    def test_short_data(self) -> None:
        info = detect(b"\x00")
        assert info.type == MediaType.UNKNOWN

    def test_short_data_two_bytes(self) -> None:
        info = detect(b"\x00\x01")
        assert info.type == MediaType.UNKNOWN

    def test_short_data_three_bytes(self) -> None:
        info = detect(b"\x00\x01\x02")
        assert info.type == MediaType.UNKNOWN


# ===========================================================================
# detect_file
# ===========================================================================
class TestDetectFile:
    def test_detect_file_png(self, tmp_path: Path) -> None:
        p = tmp_path / "test.png"
        p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        info = detect_file(p)
        assert info.type == MediaType.IMAGE
        assert info.format == "png"

    def test_detect_file_text(self, tmp_path: Path) -> None:
        p = tmp_path / "test.txt"
        p.write_bytes(b"Hello, this is text content.\n")
        info = detect_file(p)
        assert info.type == MediaType.TEXT

    def test_detect_file_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "empty"
        p.write_bytes(b"")
        info = detect_file(p)
        assert info.type == MediaType.UNKNOWN

    def test_detect_file_str_path(self, tmp_path: Path) -> None:
        p = tmp_path / "test.mp4"
        p.write_bytes(_ftyp(b"isom") + b"\x00" * 100)
        info = detect_file(str(p))
        assert info.type == MediaType.VIDEO
        assert info.format == "mp4"

    def test_detect_file_not_found(self) -> None:
        with pytest.raises((FileNotFoundError, OSError)):
            detect_file("/nonexistent/path/file.bin")


# ===========================================================================
# MediaInfo / MediaType basics
# ===========================================================================
class TestTypes:
    def test_media_info_defaults(self) -> None:
        info = MediaInfo()
        assert info.type == MediaType.UNKNOWN
        assert info.format == ""
        assert info.mime_type == ""
        assert info.container == ""

    def test_media_info_frozen(self) -> None:
        info = MediaInfo()
        with pytest.raises(AttributeError):
            info.type = MediaType.VIDEO  # type: ignore[misc]

    def test_media_type_values(self) -> None:
        assert MediaType.UNKNOWN.value == "unknown"
        assert MediaType.VIDEO.value == "video"
        assert MediaType.AUDIO.value == "audio"
        assert MediaType.IMAGE.value == "image"
        assert MediaType.TEXT.value == "text"
