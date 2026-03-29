"""Collector — orchestrates source → transform → target pipelines.

The collector:
1. Pulls items from each source (async streaming, in parallel)
2. Applies transforms (resize, compress, filter)
3. Saves items to disk organized by label
4. Publishes to targets (Kaggle, HuggingFace, etc.)

Supports incremental builds via a `.manifest.json` file in the output directory.
Sources that were already downloaded with the same config are skipped unless --force is used.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pykit_dataset.model import DataItem, Label
from pykit_dataset.source import Source
from pykit_dataset.target import PublishResult, Target
from pykit_dataset.transform import Transform

logger = logging.getLogger(__name__)

MANIFEST_FILE = ".manifest.json"


def _source_cache_key(source: Source) -> dict[str, Any]:
    """Build a cache key dict from a source's config for manifest comparison."""
    cfg = getattr(source, "_config", None)
    if cfg is None:
        return {"name": source.name}
    return {
        "name": source.name,
        "repo": getattr(cfg, "repo", ""),
        "split": getattr(cfg, "split", ""),
        "max_items": getattr(cfg, "max_items", None),
        "label_map": {str(k): int(v) for k, v in getattr(cfg, "label_map", {}).items()},
    }


def _load_manifest(output_dir: Path) -> dict[str, Any]:
    """Load the build manifest from disk."""
    path = output_dir / MANIFEST_FILE
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_manifest(output_dir: Path, manifest: dict[str, Any]) -> None:
    """Persist the build manifest to disk."""
    path = output_dir / MANIFEST_FILE
    path.write_text(json.dumps(manifest, indent=2, default=str))


@runtime_checkable
class ProgressCallback(Protocol):
    """Callback protocol for reporting collection progress."""

    def on_source_start(
        self, source_name: str, source_index: int, total_sources: int, max_items: int | None
    ) -> None: ...

    def on_item_saved(self, source_name: str, label: Label, source_count: int, total_count: int) -> None: ...

    def on_item_skipped(self, source_name: str, reason: str) -> None: ...

    def on_source_done(self, source_name: str, stats: dict[str, int]) -> None: ...

    def on_source_cached(self, source_name: str, stats: dict[str, int]) -> None:
        """Called when a source is skipped because it was already cached."""
        ...

    def on_source_error(self, source_name: str, error: Exception) -> None: ...

    def on_publish_start(self, target_name: str) -> None: ...

    def on_publish_done(self, target_name: str, result: PublishResult) -> None: ...

    def on_publish_error(self, target_name: str, error: Exception) -> None: ...


class _NullProgress:
    """No-op progress callback."""

    def on_source_start(
        self, source_name: str, source_index: int, total_sources: int, max_items: int | None
    ) -> None:
        pass

    def on_item_saved(self, source_name: str, label: Label, source_count: int, total_count: int) -> None:
        pass

    def on_item_skipped(self, source_name: str, reason: str) -> None:
        pass

    def on_source_done(self, source_name: str, stats: dict[str, int]) -> None:
        pass

    def on_source_cached(self, source_name: str, stats: dict[str, int]) -> None:
        pass

    def on_source_error(self, source_name: str, error: Exception) -> None:
        pass

    def on_publish_start(self, target_name: str) -> None:
        pass

    def on_publish_done(self, target_name: str, result: PublishResult) -> None:
        pass

    def on_publish_error(self, target_name: str, error: Exception) -> None:
        pass


@dataclass
class CollectorConfig:
    """Configuration for the collector."""

    output_dir: Path = field(default_factory=lambda: Path("/tmp/dataset_build"))
    concurrency: int = 4
    source_timeout: float = 600.0  # seconds per source, 0 = no timeout
    force: bool = False  # skip cache, re-download everything


@dataclass
class CollectorResult:
    """Result of a collection run."""

    total_items: int = 0
    real_count: int = 0
    ai_count: int = 0
    source_stats: dict[str, dict[str, int]] = field(default_factory=dict)
    cached_sources: list[str] = field(default_factory=list)
    publish_results: list[PublishResult] = field(default_factory=list)
    duration_seconds: float = 0.0
    output_dir: Path = field(default_factory=lambda: Path("."))


class Collector:
    """Orchestrate data collection from sources through transforms to targets."""

    def __init__(
        self,
        sources: list[Source],
        targets: list[Target] | None = None,
        transforms: list[Transform] | None = None,
        config: CollectorConfig | None = None,
        progress: ProgressCallback | None = None,
    ) -> None:
        self._sources = sources
        self._targets = targets or []
        self._transforms = transforms or []
        self._config = config or CollectorConfig()
        self._progress: ProgressCallback = progress or _NullProgress()
        self._file_idx = 0
        self._file_lock = threading.Lock()
        self._cancelled = False

    def cancel(self) -> None:
        """Signal all sources to stop fetching."""
        self._cancelled = True

    def _next_file_idx(self) -> int:
        with self._file_lock:
            idx = self._file_idx
            self._file_idx += 1
            return idx

    def _is_source_cached(self, source: Source, manifest: dict[str, Any]) -> dict[str, int] | None:
        """Check if a source was already completed with the same config. Returns cached stats or None."""
        cached = manifest.get("sources", {}).get(source.name)
        if cached is None:
            return None
        current_key = _source_cache_key(source)
        if cached.get("config") == current_key and cached.get("status") == "done":
            return cached.get("stats")
        return None

    async def _fetch_one(
        self,
        source: Source,
        src_idx: int,
        total_sources: int,
        real_dir: Path,
        ai_dir: Path,
        result: CollectorResult,
        result_lock: asyncio.Lock,
        manifest: dict[str, Any],
        manifest_lock: threading.Lock,
    ) -> dict[str, int]:
        """Fetch items from a single source."""
        progress = self._progress
        max_items = getattr(getattr(source, "_config", None), "max_items", None)
        progress.on_source_start(source.name, src_idx, total_sources, max_items)
        logger.info("Fetching from %s", source.name)
        src_real = 0
        src_ai = 0

        try:
            timeout = self._config.source_timeout
            deadline = time.monotonic() + timeout if timeout > 0 else float("inf")

            async for item in source.fetch():
                if self._cancelled:
                    logger.info("Cancelled, stopping %s", source.name)
                    break

                if timeout > 0 and time.monotonic() > deadline:
                    logger.warning("Timeout for %s after %.0fs", source.name, timeout)
                    break

                # Apply transforms
                transformed: DataItem | None = item
                for t in self._transforms:
                    if transformed is None:
                        break
                    transformed = t.apply(transformed)
                if transformed is None:
                    progress.on_item_skipped(source.name, "filtered by transform")
                    continue

                # Save to disk with unique filename
                file_idx = self._next_file_idx()
                subdir = real_dir if transformed.label == Label.REAL else ai_dir
                path = subdir / f"{file_idx:06d}{transformed.extension}"
                path.write_bytes(transformed.content)

                if transformed.label == Label.REAL:
                    src_real += 1
                else:
                    src_ai += 1

                async with result_lock:
                    if transformed.label == Label.REAL:
                        result.real_count += 1
                    else:
                        result.ai_count += 1
                    result.total_items += 1
                    total_count = result.total_items

                progress.on_item_saved(
                    source.name,
                    transformed.label,
                    src_real + src_ai,
                    total_count,
                )

                # Yield control so other sources can run
                if (src_real + src_ai) % 10 == 0:
                    await asyncio.sleep(0)

        except Exception as exc:
            logger.exception("Error fetching from %s", source.name)
            progress.on_source_error(source.name, exc)

        src_stats = {"total": src_real + src_ai, "real": src_real, "ai": src_ai}
        async with result_lock:
            result.source_stats[source.name] = src_stats
        progress.on_source_done(source.name, src_stats)

        # Update manifest so this source is cached for next run
        with manifest_lock:
            manifest.setdefault("sources", {})[source.name] = {
                "config": _source_cache_key(source),
                "stats": src_stats,
                "status": "done" if not self._cancelled else "partial",
            }
            _save_manifest(self._config.output_dir, manifest)

        logger.info(
            "  %s: %d items (real=%d, ai=%d)",
            source.name,
            src_real + src_ai,
            src_real,
            src_ai,
        )
        return src_stats

    async def run(self) -> CollectorResult:
        """Execute the full collection pipeline."""
        start = time.monotonic()
        cfg = self._config
        out = cfg.output_dir

        # Prepare output directories
        real_dir = out / "real"
        ai_dir = out / "ai"
        real_dir.mkdir(parents=True, exist_ok=True)
        ai_dir.mkdir(parents=True, exist_ok=True)

        result = CollectorResult(output_dir=out)
        result_lock = asyncio.Lock()
        total_sources = len(self._sources)

        # Load manifest for cache checking
        manifest = _load_manifest(out) if not cfg.force else {}
        manifest_lock = threading.Lock()

        # Check which sources need fetching vs cached
        sources_to_fetch: list[tuple[int, Source]] = []
        for idx, source in enumerate(self._sources):
            if not cfg.force:
                cached_stats = self._is_source_cached(source, manifest)
                if cached_stats is not None:
                    logger.info("Cached: %s (%d items)", source.name, cached_stats["total"])
                    result.source_stats[source.name] = cached_stats
                    result.total_items += cached_stats["total"]
                    result.real_count += cached_stats["real"]
                    result.ai_count += cached_stats["ai"]
                    result.cached_sources.append(source.name)
                    self._progress.on_source_cached(source.name, cached_stats)
                    continue
            sources_to_fetch.append((idx, source))

        if not sources_to_fetch:
            logger.info("All sources cached, nothing to fetch")
        else:
            # Adjust file index past existing files to avoid collisions on incremental builds
            existing_real = len(list(real_dir.glob("*"))) if real_dir.exists() else 0
            existing_ai = len(list(ai_dir.glob("*"))) if ai_dir.exists() else 0
            self._file_idx = existing_real + existing_ai

            # Fetch sources sequentially — HF sources use asyncio.to_thread internally
            # so the event loop stays responsive for progress display updates
            for idx, source in sources_to_fetch:
                if self._cancelled:
                    break
                await self._fetch_one(
                    source,
                    idx,
                    total_sources,
                    real_dir,
                    ai_dir,
                    result,
                    result_lock,
                    manifest,
                    manifest_lock,
                )

        # Publish to targets
        for target in self._targets:
            if self._cancelled:
                break
            self._progress.on_publish_start(target.name)
            logger.info("Publishing to %s", target.name)
            try:
                pub = await target.publish(out)
                result.publish_results.append(pub)
                self._progress.on_publish_done(target.name, pub)
                logger.info("  %s: %s", target.name, pub.location)
            except Exception as exc:
                logger.exception("Error publishing to %s", target.name)
                self._progress.on_publish_error(target.name, exc)

        result.duration_seconds = time.monotonic() - start
        logger.info(
            "Done: %d items (real=%d, ai=%d) in %.1fs",
            result.total_items,
            result.real_count,
            result.ai_count,
            result.duration_seconds,
        )
        return result
