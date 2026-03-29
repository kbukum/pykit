"""HuggingFace datasets source — stream from any HF dataset.

Requires: ``pip install datasets huggingface-hub Pillow``

Example::

    source = HuggingFaceSource(
        repo="dragonintelligence/CIFAKE-image-dataset",
        split="train",
        image_col="image",
        label_col="label",
        label_map={0: Label.AI_GENERATED, 1: Label.REAL},
        max_items=1000,
    )
    async for item in source.fetch():
        print(item.label, len(item.content))
"""

from __future__ import annotations

import asyncio
import io
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pykit_dataset.model import DataItem, Label, MediaType

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HuggingFaceSourceConfig:
    """Configuration for a single HuggingFace dataset source."""

    repo: str
    split: str = "train"
    image_col: str = "image"
    label_col: str | None = "label"
    label_map: dict[int | str, Label] = field(default_factory=dict)
    max_items: int | None = None
    token: bool = False
    shuffle_buffer: int = 200


def _load_and_shuffle(repo: str, split: str, token: bool, buffer_size: int):
    """Load dataset in a thread (blocking I/O)."""
    from datasets import load_dataset

    ds = load_dataset(repo, split=split, streaming=True, token=token)
    return ds.shuffle(seed=42, buffer_size=buffer_size)


def _next_row(ds_iter):
    """Get next row from dataset iterator (blocking I/O)."""
    try:
        return next(ds_iter)
    except StopIteration:
        return None


class HuggingFaceSource:
    """Stream data items from a HuggingFace dataset.

    Uses ``datasets`` library in streaming mode for constant memory usage.
    Supports per-class balancing for datasets with ordered shards.
    The blocking HF I/O is offloaded to threads so the event loop stays responsive.
    """

    def __init__(self, config: HuggingFaceSourceConfig) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return f"hf:{self._config.repo}"

    async def fetch(self) -> AsyncIterator[DataItem]:
        """Stream items from HuggingFace dataset."""
        from PIL import Image

        cfg = self._config
        logger.info("Loading %s (split=%s, max=%s)", cfg.repo, cfg.split, cfg.max_items)

        try:
            ds = await asyncio.to_thread(
                _load_and_shuffle, cfg.repo, cfg.split, cfg.token, cfg.shuffle_buffer,
            )
        except Exception as exc:
            logger.warning("Failed to load %s: %s", cfg.repo, exc)
            return

        max_n = cfg.max_items or float("inf")
        has_both_classes = cfg.label_col is not None and "all" not in cfg.label_map
        per_class_max = max_n // 2 if (has_both_classes and max_n != float("inf")) else float("inf")

        count = 0
        class_counts: dict[int, int] = {0: 0, 1: 0}
        ds_iter = iter(ds)

        while count < max_n:
            # Offload blocking next() to thread so event loop stays free
            row = await asyncio.to_thread(_next_row, ds_iter)
            if row is None:
                break

            # Extract image
            raw_img = row.get(cfg.image_col)
            if raw_img is None:
                continue

            try:
                if isinstance(raw_img, Image.Image):
                    img = raw_img.convert("RGB")
                else:
                    img = Image.open(io.BytesIO(raw_img)).convert("RGB")
            except Exception:
                continue

            # Extract label
            if "all" in cfg.label_map:
                label = cfg.label_map["all"]
            elif cfg.label_col and cfg.label_col in row:
                raw_label = row[cfg.label_col]
                if raw_label not in cfg.label_map:
                    continue
                label = cfg.label_map[raw_label]
            else:
                continue

            if label not in (Label.REAL, Label.AI_GENERATED):
                continue

            # Per-class balance enforcement
            if has_both_classes and class_counts[int(label)] >= per_class_max:
                continue

            # Encode to JPEG bytes
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=95)
            content = buf.getvalue()

            class_counts[int(label)] += 1
            count += 1

            yield DataItem(
                content=content,
                label=label,
                media_type=MediaType.IMAGE,
                source_name=self.name,
                extension=".jpg",
                metadata={"repo": cfg.repo, "split": cfg.split},
            )

        logger.info("  %s: %d items (real=%d, ai=%d)", cfg.repo, count, class_counts[0], class_counts[1])
