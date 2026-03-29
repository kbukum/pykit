"""Dataset module — reusable data collection, transformation, and publishing.

Provides protocol-based abstractions for:
- **Sources**: pull data from HuggingFace, web crawlers, local directories
- **Targets**: publish data to Kaggle, HuggingFace, or local disk
- **Transforms**: resize, compress, augment data items
- **Collector**: orchestrate source → transform → target pipelines

Example::

    from pykit_dataset import Collector, CollectorConfig
    from pykit_dataset.sources.huggingface import HuggingFaceSource
    from pykit_dataset.targets.local import LocalTarget

    sources = [HuggingFaceSource(repo="org/dataset", split="train", max_samples=1000)]
    target = LocalTarget(directory="/tmp/dataset")
    collector = Collector(sources=sources, target=target)
    result = await collector.run()
"""

from __future__ import annotations

from pykit_dataset.collector import Collector, CollectorConfig, CollectorResult, ProgressCallback
from pykit_dataset.model import DataItem, Label, MediaType
from pykit_dataset.source import Source
from pykit_dataset.target import Target
from pykit_dataset.transform import Transform

__all__ = [
    "Collector",
    "CollectorConfig",
    "CollectorResult",
    "DataItem",
    "Label",
    "MediaType",
    "ProgressCallback",
    "Source",
    "Target",
    "Transform",
]
