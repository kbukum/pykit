"""Source protocol — pull data from any origin.

Sources are async generators that yield ``DataItem`` instances.
Each source is responsible for:
- Connecting to its data origin (HuggingFace, web API, local disk, etc.)
- Yielding items one at a time (memory-efficient streaming)
- Respecting the requested ``max_items`` limit
- Setting correct labels and metadata on each item
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from pykit_dataset.model import DataItem


@runtime_checkable
class Source(Protocol):
    """Protocol for dataset sources.

    Mirrors ``pykit.provider.Provider`` pattern with ``name`` + async operation.
    """

    @property
    def name(self) -> str:
        """Unique identifier for this source."""
        ...

    def fetch(self) -> AsyncIterator[DataItem]:
        """Yield data items from the source.

        This is an async generator. Items are yielded one at a time
        to keep memory usage constant regardless of dataset size.
        """
        ...
