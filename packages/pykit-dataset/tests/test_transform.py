"""Additional tests for Transform protocol and ResizeTransform."""

from __future__ import annotations

import io

from pykit_dataset.model import DataItem, Label, MediaType
from pykit_dataset.transform import ResizeTransform, Transform

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_jpeg_item(width: int = 64, height: int = 64, label: Label = Label.REAL) -> DataItem:
    """Create a DataItem with valid JPEG content."""
    from PIL import Image

    img = Image.new("RGB", (width, height), color=(128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return DataItem(
        content=buf.getvalue(),
        label=label,
        media_type=MediaType.IMAGE,
        source_name="test",
        extension=".jpg",
        metadata={"key": "value"},
    )


# ===========================================================================
# Transform protocol tests
# ===========================================================================


class TestTransformProtocol:
    def test_resize_implements_protocol(self):
        """ResizeTransform is recognized as implementing Transform protocol."""
        transform = ResizeTransform()
        assert isinstance(transform, Transform)

    def test_custom_class_implements_protocol(self):
        """A custom class with name and apply satisfies the protocol."""

        class MyTransform:
            @property
            def name(self) -> str:
                return "my-transform"

            def apply(self, item: DataItem) -> DataItem | None:
                return item

        t = MyTransform()
        assert isinstance(t, Transform)

    def test_class_missing_apply_does_not_implement(self):
        """A class missing apply() does not satisfy the protocol."""

        class Incomplete:
            @property
            def name(self) -> str:
                return "incomplete"

        obj = Incomplete()
        assert not isinstance(obj, Transform)

    def test_class_missing_name_does_not_implement(self):
        """A class missing name property does not satisfy the protocol."""

        class NoName:
            def apply(self, item: DataItem) -> DataItem | None:
                return item

        obj = NoName()
        assert not isinstance(obj, Transform)


# ===========================================================================
# ResizeTransform tests
# ===========================================================================


class TestResizeTransform:
    def test_name_default(self):
        t = ResizeTransform()
        assert t.name == "resize-256x256"

    def test_name_custom(self):
        t = ResizeTransform(width=128, height=64)
        assert t.name == "resize-128x64"

    def test_apply_resizes_image(self):
        """apply() resizes the image to the specified dimensions."""
        from PIL import Image

        item = _make_jpeg_item(100, 80)
        t = ResizeTransform(width=32, height=32, quality=90)
        result = t.apply(item)

        assert result is not None
        assert result.label == Label.REAL
        assert result.media_type == MediaType.IMAGE
        assert result.extension == ".jpg"
        assert result.source_name == "test"
        assert result.metadata == {"key": "value"}

        # Verify actual dimensions
        img = Image.open(io.BytesIO(result.content))
        assert img.size == (32, 32)

    def test_apply_preserves_label(self):
        """apply() preserves the original label."""
        item = _make_jpeg_item(label=Label.AI_GENERATED)
        t = ResizeTransform(width=16, height=16)
        result = t.apply(item)

        assert result is not None
        assert result.label == Label.AI_GENERATED

    def test_apply_invalid_content_returns_none(self):
        """Invalid image content returns None (filtering)."""
        item = DataItem(
            content=b"not-an-image",
            label=Label.REAL,
            media_type=MediaType.IMAGE,
            source_name="test",
            extension=".jpg",
        )
        t = ResizeTransform()
        result = t.apply(item)
        assert result is None

    def test_apply_empty_content_returns_none(self):
        """Empty content returns None."""
        item = DataItem(
            content=b"",
            label=Label.REAL,
            media_type=MediaType.IMAGE,
            source_name="test",
        )
        t = ResizeTransform()
        result = t.apply(item)
        assert result is None

    def test_apply_output_is_jpeg(self):
        """Output is always JPEG regardless of input format."""
        from PIL import Image

        # Create a PNG input
        img = Image.new("RGB", (50, 50), color=(0, 0, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        item = DataItem(
            content=buf.getvalue(),
            label=Label.REAL,
            media_type=MediaType.IMAGE,
            source_name="test",
            extension=".png",
        )

        t = ResizeTransform(width=24, height=24)
        result = t.apply(item)

        assert result is not None
        assert result.extension == ".jpg"
        # Verify it's valid JPEG
        out_img = Image.open(io.BytesIO(result.content))
        assert out_img.format == "JPEG"

    def test_apply_different_qualities(self):
        """Different quality settings produce different output sizes."""
        # Use a noisy image so quality differences are measurable
        import random

        from PIL import Image

        random.seed(42)
        img = Image.new("RGB", (128, 128))
        pixels = img.load()
        for x in range(128):
            for y in range(128):
                pixels[x, y] = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        item = DataItem(
            content=buf.getvalue(),
            label=Label.REAL,
            media_type=MediaType.IMAGE,
            source_name="test",
            extension=".jpg",
            metadata={"key": "value"},
        )

        t_low = ResizeTransform(width=64, height=64, quality=10)
        t_high = ResizeTransform(width=64, height=64, quality=95)

        result_low = t_low.apply(item)
        result_high = t_high.apply(item)

        assert result_low is not None
        assert result_high is not None
        # Higher quality should produce larger output for a noisy image
        assert len(result_high.content) > len(result_low.content)

    def test_apply_rgba_input_converted_to_rgb(self):
        """RGBA input is converted to RGB."""
        from PIL import Image

        img = Image.new("RGBA", (50, 50), color=(255, 0, 0, 128))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        item = DataItem(
            content=buf.getvalue(),
            label=Label.REAL,
            media_type=MediaType.IMAGE,
            source_name="test",
            extension=".png",
        )

        t = ResizeTransform(width=24, height=24)
        result = t.apply(item)

        assert result is not None
        out_img = Image.open(io.BytesIO(result.content))
        assert out_img.mode == "RGB"


class TestTransformAsFilter:
    """Test Transform used as a filter (returning None to discard)."""

    def test_filter_transform(self):
        """A transform that returns None filters out items."""

        class RejectAll:
            @property
            def name(self) -> str:
                return "reject-all"

            def apply(self, item: DataItem) -> DataItem | None:
                return None

        t = RejectAll()
        item = _make_jpeg_item()
        assert t.apply(item) is None

    def test_passthrough_transform(self):
        """A transform that returns the item unchanged."""

        class Passthrough:
            @property
            def name(self) -> str:
                return "passthrough"

            def apply(self, item: DataItem) -> DataItem | None:
                return item

        t = Passthrough()
        item = _make_jpeg_item()
        result = t.apply(item)
        assert result is item
