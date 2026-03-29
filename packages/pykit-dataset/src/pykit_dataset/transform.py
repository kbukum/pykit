"""Transform protocol and built-in transforms.

Transforms modify ``DataItem`` instances in the pipeline.
Return ``None`` to discard an item (filtering).
"""

from __future__ import annotations

import io
from typing import Protocol, runtime_checkable

from pykit_dataset.model import DataItem


@runtime_checkable
class Transform(Protocol):
    """Protocol for data transforms."""

    @property
    def name(self) -> str:
        """Human-readable transform name."""
        ...

    def apply(self, item: DataItem) -> DataItem | None:
        """Transform an item. Return ``None`` to discard."""
        ...


class ResizeTransform:
    """Resize images to a fixed size and re-encode as JPEG.

    Requires Pillow (``pip install Pillow``).
    """

    def __init__(self, width: int = 256, height: int = 256, quality: int = 85) -> None:
        self._width = width
        self._height = height
        self._quality = quality

    @property
    def name(self) -> str:
        return f"resize-{self._width}x{self._height}"

    def apply(self, item: DataItem) -> DataItem | None:
        from PIL import Image

        try:
            img = Image.open(io.BytesIO(item.content)).convert("RGB")
            img = img.resize((self._width, self._height), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=self._quality)
            return DataItem(
                content=buf.getvalue(),
                label=item.label,
                media_type=item.media_type,
                source_name=item.source_name,
                extension=".jpg",
                metadata=item.metadata,
            )
        except Exception:
            return None
