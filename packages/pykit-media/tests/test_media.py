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


# ===========================================================================
# Security / malicious file detection
# ===========================================================================
class TestSecurityDetection:
    def test_script_embedded_in_jpeg(self) -> None:
        data = b"\xff\xd8\xff\xe0" + b"\x00" * 50 + b"<script>alert(1)</script>"
        info = detect(data)
        assert info.type == MediaType.IMAGE
        assert info.format == "jpeg"

    def test_php_inside_gif(self) -> None:
        data = b"GIF89a" + b"\x00" * 50 + b'<?php echo("hacked"); ?>'
        info = detect(data)
        assert info.type == MediaType.IMAGE
        assert info.format == "gif"

    def test_polyglot_pdf_jpeg(self) -> None:
        data = b"\xff\xd8\xff\xe0" + b"\x00" * 100 + b"%PDF-1.4"
        info = detect(data)
        assert info.type == MediaType.IMAGE
        assert info.format == "jpeg"

    def test_null_byte_padding(self) -> None:
        data = b"\x00" * 1000
        info = detect(data)
        assert info.type == MediaType.UNKNOWN

    def test_script_inside_png(self) -> None:
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50 + b"<script>"
        info = detect(data)
        assert info.type == MediaType.IMAGE
        assert info.format == "png"

    def test_svg_script_not_detected_as_text(self) -> None:
        data = b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>"
        info = detect(data)
        assert info.type == MediaType.TEXT
        assert info.format == "txt"

    def test_html_script_tags(self) -> None:
        data = b"<html><script>alert(1)</script></html>"
        info = detect(data)
        assert info.type == MediaType.TEXT
        assert info.format == "txt"

    def test_binary_with_embedded_elf(self) -> None:
        data = b"\x7fELF" + bytes(range(256)) * 4
        info = detect(data)
        assert info.type == MediaType.UNKNOWN


# ===========================================================================
# Additional edge cases
# ===========================================================================
class TestEdgeCases:
    def test_exactly_four_bytes_random(self) -> None:
        data = b"\xde\xad\xbe\xef"
        info = detect(data)
        assert info.type == MediaType.UNKNOWN

    def test_repeated_magic_bytes(self) -> None:
        # JPEG magic followed by PNG magic — JPEG is detected first (image detector)
        data = b"\xff\xd8\xff\xe0" + b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        info = detect(data)
        assert info.type == MediaType.IMAGE
        assert info.format == "jpeg"

    def test_max_detect_bytes_limit(self) -> None:
        data = b"A" * 5000  # >4096 bytes, all printable
        info = detect(data)
        assert info.type == MediaType.TEXT

    def test_text_boundary_95_percent(self) -> None:
        # 95% printable, 5% control chars (not \t\n\r)
        printable = b"A" * 95
        control = bytes([0x01]) * 5  # non-printable, non-whitespace control
        data = printable + control
        info = detect(data)
        assert info.type == MediaType.TEXT
        assert info.format == "txt"

    def test_text_below_boundary(self) -> None:
        # ~90% printable, 10% control chars → below 95% threshold
        printable = b"A" * 90
        control = bytes([0x01]) * 10
        data = printable + control
        info = detect(data)
        assert info.type == MediaType.UNKNOWN

    def test_all_whitespace(self) -> None:
        data = b"   \t\t\n\n\r\r  \t  \n"
        info = detect(data)
        assert info.type == MediaType.TEXT

    def test_only_newlines(self) -> None:
        data = b"\n" * 100
        info = detect(data)
        assert info.type == MediaType.TEXT

    def test_detect_file_large_file(self, tmp_path: Path) -> None:
        # PNG header + >4096 bytes of padding
        p = tmp_path / "large.png"
        p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8000)
        info = detect_file(p)
        assert info.type == MediaType.IMAGE
        assert info.format == "png"

    def test_single_null_byte(self) -> None:
        info = detect(b"\x00")
        assert info.type == MediaType.UNKNOWN

    def test_gif87a_variant(self) -> None:
        data = b"GIF87a" + b"\x00" * 100
        info = detect(data)
        assert info.type == MediaType.IMAGE
        assert info.format == "gif"
        assert info.mime_type == "image/gif"
        assert info.container == "gif"


# ===========================================================================
# Container field verification
# ===========================================================================
class TestContainerFields:
    def test_avi_container(self) -> None:
        data = b"RIFF" + b"\x00" * 4 + b"AVI " + b"\x00" * 100
        info = detect(data)
        assert info.container == "avi"

    def test_wav_container(self) -> None:
        data = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 100
        info = detect(data)
        assert info.container == "riff"

    def test_webp_container(self) -> None:
        data = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 100
        info = detect(data)
        assert info.container == "riff"

    def test_mp4_container(self) -> None:
        info = detect(_ftyp(b"isom"))
        assert info.container == "mp4"

    def test_text_no_container(self) -> None:
        info = detect(b"Hello, this is plain text.\n")
        assert info.container == ""

    def test_unknown_no_container(self) -> None:
        info = detect(b"")
        assert info.container == ""


# ===========================================================================
# MIME type completeness
# ===========================================================================
class TestMimeTypeCompleteness:
    @pytest.mark.parametrize(
        ("data", "expected_mime"),
        [
            # Video formats
            (_ftyp(b"isom"), "video/mp4"),
            (_ftyp(b"qt  "), "video/quicktime"),
            (_ftyp(b"M4V "), "video/x-m4v"),
            (
                b"\x1a\x45\xdf\xa3" + b"\x00" * 10 + b"webm" + b"\x00" * 20,
                "video/webm",
            ),
            (b"\x1a\x45\xdf\xa3" + b"\x00" * 60, "video/x-matroska"),
            (b"RIFF" + b"\x00" * 4 + b"AVI " + b"\x00" * 100, "video/x-msvideo"),
            (b"FLV\x01\x05" + b"\x00" * 100, "video/x-flv"),
            (
                b"\x47" + b"\x00" * 187 + b"\x47" + b"\x00" * 100,
                "video/mp2t",
            ),
            # Audio formats
            (b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 100, "audio/wav"),
            (b"fLaC" + b"\x00" * 100, "audio/flac"),
            (b"OggS" + b"\x00" * 100, "audio/ogg"),
            (b"\xff\xf1" + b"\x00" * 100, "audio/aac"),
            (b"ID3\x04\x00" + b"\x00" * 100, "audio/mpeg"),
            (b"\xff\xfb" + b"\x00" * 100, "audio/mpeg"),
            (b"MThd" + b"\x00" * 100, "audio/midi"),
            (b"FORM" + b"\x00" * 4 + b"AIFF" + b"\x00" * 100, "audio/aiff"),
            (_ftyp(b"M4A "), "audio/mp4"),
            (_ftyp(b"M4B "), "audio/mp4"),
            # Image formats
            (b"\xff\xd8\xff\xe0" + b"\x00" * 100, "image/jpeg"),
            (b"\x89PNG\r\n\x1a\n" + b"\x00" * 100, "image/png"),
            (b"GIF89a" + b"\x00" * 100, "image/gif"),
            (b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 100, "image/webp"),
            (b"BM" + b"\x00" * 100, "image/bmp"),
            (b"II\x2a\x00" + b"\x00" * 100, "image/tiff"),
            (b"MM\x00\x2a" + b"\x00" * 100, "image/tiff"),
            (b"\x00\x00\x01\x00" + b"\x00" * 100, "image/x-icon"),
            (_ftyp(b"avif"), "image/avif"),
            (_ftyp(b"heic"), "image/heif"),
            # Text
            (b"Hello, world!\n", "text/plain"),
        ],
        ids=[
            "mp4",
            "mov",
            "m4v",
            "webm",
            "mkv",
            "avi",
            "flv",
            "ts",
            "wav",
            "flac",
            "ogg",
            "aac",
            "mp3-id3",
            "mp3-sync",
            "midi",
            "aiff",
            "m4a",
            "m4b",
            "jpeg",
            "png",
            "gif",
            "webp",
            "bmp",
            "tiff-le",
            "tiff-be",
            "ico",
            "avif",
            "heif",
            "text",
        ],
    )
    def test_mime_type(self, data: bytes, expected_mime: str) -> None:
        info = detect(data)
        assert info.mime_type == expected_mime


# ===========================================================================
# MediaInfo frozen dataclass equality and hashing
# ===========================================================================
class TestMediaInfoEquality:
    def test_media_info_equality(self) -> None:
        a = MediaInfo(type=MediaType.IMAGE, format="png", mime_type="image/png", container="png")
        b = MediaInfo(type=MediaType.IMAGE, format="png", mime_type="image/png", container="png")
        assert a == b

    def test_media_info_inequality(self) -> None:
        a = MediaInfo(type=MediaType.IMAGE, format="png", mime_type="image/png", container="png")
        b = MediaInfo(type=MediaType.IMAGE, format="jpeg", mime_type="image/jpeg", container="jpeg")
        assert a != b

    def test_media_info_hash(self) -> None:
        a = MediaInfo(type=MediaType.IMAGE, format="png", mime_type="image/png", container="png")
        b = MediaInfo(type=MediaType.IMAGE, format="png", mime_type="image/png", container="png")
        assert hash(a) == hash(b)
        # Can be used in sets/dicts
        s = {a, b}
        assert len(s) == 1
