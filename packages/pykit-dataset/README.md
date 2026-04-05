# pykit-dataset

Reusable data collection, transformation, and publishing framework with protocol-based abstractions for building ML dataset pipelines.

## Installation

```bash
pip install pykit-dataset
# or
uv add pykit-dataset
```

Optional extras for specific sources/targets:

```bash
pip install pykit-dataset[huggingface]   # HuggingFace datasets
pip install pykit-dataset[kaggle]        # Kaggle uploads
pip install pykit-dataset[web]           # Web scraping (DuckDuckGo)
pip install pykit-dataset[all]           # Everything
```

## Quick Start

```python
import asyncio
from pathlib import Path
from pykit_dataset import Collector, CollectorConfig, Source, Label, MediaType
from pykit_dataset.sources.local import LocalSource
from pykit_dataset.targets.local import LocalTarget

# Build a pipeline: collect from local dirs, publish locally
collector = Collector(
    sources=[
        LocalSource(Path("data/real"), label=Label.REAL, media_type=MediaType.IMAGE),
        LocalSource(Path("data/ai"), label=Label.AI_GENERATED),
    ],
    targets=[LocalTarget()],
    config=CollectorConfig(output_dir=Path("output/dataset"), concurrency=4),
)

result = asyncio.run(collector.run())
print(f"Collected {result.total_items} items in {result.duration_seconds:.1f}s")
print(f"  Real: {result.real_count}, AI: {result.ai_count}")
```

## Key Components

- **Source** — Protocol for async data sources; implement `name` and `async fetch() -> AsyncIterator[DataItem]` for streaming
- **Target** — Protocol for publishing; implement `name` and `async publish(directory, metadata) -> PublishResult`
- **Transform** — Protocol for item modification/filtering; implement `name` and `apply(item) -> DataItem | None` (return `None` to discard)
- **Collector** — Orchestrates source → transform → target pipelines with concurrent source fetching, incremental caching (`.manifest.json`), and cancellation support
- **CollectorConfig** — Pipeline config: `output_dir`, `concurrency`, `source_timeout`, `force` (skip cache)
- **DataItem** — Frozen dataclass: `content` (bytes), `label`, `media_type`, `source_name`, `extension`, `metadata`
- **Label** — IntEnum: `REAL = 0`, `AI_GENERATED = 1`
- **MediaType** — StrEnum: `IMAGE`, `TEXT`, `AUDIO`, `VIDEO`
- **ProgressCallback** — Protocol for tracking pipeline progress with per-source and per-target events

### Built-in Sources & Targets

- **LocalSource** — Load from local directories with extension filtering
- **WebSource** — Fetch images from DuckDuckGo (no API key required)
- **HuggingFaceSource** — Stream from HuggingFace datasets in constant memory
- **LocalTarget / KaggleTarget / HuggingFaceTarget** — Publish to disk, Kaggle, or HuggingFace Hub

## Dependencies

Core package has no dependencies (protocols only). Optional extras install:
- `datasets`, `huggingface-hub`, `Pillow` (HuggingFace)
- `kagglehub` (Kaggle)
- `httpx`, `Pillow` (web scraping)

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
