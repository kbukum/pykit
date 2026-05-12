"""Chunked transcription orchestrator — parallel transcription with progress."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from pathlib import Path

from pykit_errors import AppError, ErrorCode
from pykit_transcription.chunking import merge_segments, plan_chunks
from pykit_transcription.protocol import TranscriptionBackend
from pykit_transcription.types import (
    ChunkPlan,
    TranscriptionConfig,
    TranscriptionProgress,
    TranscriptResult,
    TranscriptSegment,
)


class ChunkedTranscriber:
    """Orchestrates chunked parallel transcription.

    Splits audio at silence boundaries (if available) or fixed intervals,
    transcribes chunks in parallel with bounded concurrency, and merges
    the results into a unified transcript.

    Args:
        backend: Transcription engine implementing TranscriptionBackend.
        config: Transcription configuration.
    """

    def __init__(
        self,
        backend: TranscriptionBackend,
        config: TranscriptionConfig | None = None,
    ) -> None:
        self._backend = backend
        self._config = config or TranscriptionConfig()

    async def transcribe(
        self,
        audio_path: str | Path,
        duration_secs: float,
        silence_points: list[float] | None = None,
        on_progress: Callable[[TranscriptionProgress], None] | None = None,
    ) -> TranscriptResult:
        """Transcribe an audio file using chunked parallel processing.

        Args:
            audio_path: Path to the source audio file.
            duration_secs: Total audio duration in seconds (from probe).
            silence_points: Optional silence midpoint timestamps for
                intelligent chunking (from silence detection).
            on_progress: Optional callback for progress updates.

        Returns:
            Complete transcription result with merged segments.

        Raises:
            AppError: If no chunks could be transcribed.
        """
        audio_path = Path(audio_path)
        chunks = plan_chunks(duration_secs, self._config, silence_points)

        if not chunks:
            return TranscriptResult(
                segments=(),
                language=self._config.language.value,
                duration_secs=duration_secs,
                model=self._config.model,
            )

        progress = TranscriptionProgress(total_chunks=len(chunks))
        start_time = time.monotonic()

        semaphore = asyncio.Semaphore(self._config.max_concurrent)
        results: list[tuple[ChunkPlan, list[TranscriptSegment]]] = []

        async def process_chunk(chunk: ChunkPlan) -> None:
            async with semaphore:
                progress.current_chunk = chunk.index
                try:
                    segments = await self._backend.transcribe_chunk(audio_path, self._config)
                    results.append((chunk, segments))
                except Exception as exc:
                    progress.errors.append(f"Chunk {chunk.index}: {exc}")
                finally:
                    progress.completed_chunks += 1
                    progress.elapsed_secs = time.monotonic() - start_time
                    if on_progress:
                        on_progress(progress)

        await asyncio.gather(*(process_chunk(c) for c in chunks))

        if not results:
            raise AppError(
                code=ErrorCode.INTERNAL,
                message=f"All {len(chunks)} chunks failed: {progress.errors}",
            )

        merged = merge_segments(results)

        return TranscriptResult(
            segments=merged,
            language=self._config.language.value,
            duration_secs=duration_secs,
            model=self._config.model,
        )
