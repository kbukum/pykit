"""Audio chunk planning and transcript segment merging.

Splits audio into chunks at optimal boundaries (silence points or fixed
intervals) and merges per-chunk transcription results into a unified
transcript with corrected timestamps.
"""

from __future__ import annotations

from pykit_transcription.types import (
    ChunkPlan,
    TranscriptionConfig,
    TranscriptSegment,
    TranscriptWord,
)


def plan_chunks(
    duration_secs: float,
    config: TranscriptionConfig,
    silence_points: list[float] | None = None,
) -> list[ChunkPlan]:
    """Plan audio chunks for parallel transcription.

    If silence points are provided, chunks are split at silence boundaries
    near the target chunk duration. Otherwise, uses fixed-duration splitting.

    Args:
        duration_secs: Total audio duration in seconds.
        config: Transcription configuration with chunk_duration_secs.
        silence_points: Optional sorted list of silence midpoint timestamps
            in seconds (from silence detection).

    Returns:
        Ordered list of chunk plans covering the full duration.
    """
    if duration_secs <= 0:
        return []

    target = config.chunk_duration_secs
    if duration_secs <= target:
        return [ChunkPlan(index=0, start_secs=0.0, end_secs=duration_secs)]

    if silence_points:
        return _plan_at_silence(duration_secs, target, silence_points)
    return _plan_fixed(duration_secs, target)


def merge_segments(
    chunk_results: list[tuple[ChunkPlan, list[TranscriptSegment]]],
) -> tuple[TranscriptSegment, ...]:
    """Merge per-chunk transcript segments into a unified timeline.

    Adjusts each segment's timestamps by the chunk's start offset so
    all segments are relative to the original source start.

    Args:
        chunk_results: List of (chunk_plan, segments) pairs, ordered by
            chunk index.

    Returns:
        Merged segments ordered by time, with corrected timestamps.
    """
    merged: list[TranscriptSegment] = []

    for chunk, segments in sorted(chunk_results, key=lambda cr: cr[0].index):
        offset = chunk.start_secs
        for seg in segments:
            shifted_words = tuple(
                TranscriptWord(
                    text=w.text,
                    start_secs=w.start_secs + offset,
                    end_secs=w.end_secs + offset,
                    confidence=w.confidence,
                )
                for w in seg.words
            )
            merged.append(
                TranscriptSegment(
                    text=seg.text,
                    start_secs=seg.start_secs + offset,
                    end_secs=seg.end_secs + offset,
                    language=seg.language,
                    confidence=seg.confidence,
                    words=shifted_words,
                    speaker=seg.speaker,
                )
            )

    return tuple(merged)


# ── Internal helpers ─────────────────────────────────────────────────────────


def _plan_fixed(duration_secs: float, target: float) -> list[ChunkPlan]:
    """Split into equal fixed-duration chunks."""
    chunks: list[ChunkPlan] = []
    start = 0.0
    index = 0

    while start < duration_secs:
        end = min(start + target, duration_secs)
        chunks.append(ChunkPlan(index=index, start_secs=start, end_secs=end))
        start = end
        index += 1

    return chunks


def _plan_at_silence(
    duration_secs: float,
    target: float,
    silence_points: list[float],
) -> list[ChunkPlan]:
    """Split at silence points nearest to target chunk boundaries.

    Searches for the closest silence point within a tolerance window
    (±30% of target duration) around each ideal split point.
    """
    tolerance = target * 0.3
    chunks: list[ChunkPlan] = []
    start = 0.0
    index = 0

    while start < duration_secs:
        ideal_end = start + target

        if ideal_end >= duration_secs:
            chunks.append(ChunkPlan(index=index, start_secs=start, end_secs=duration_secs))
            break

        best = _find_nearest_silence(ideal_end, tolerance, silence_points)
        end = best if best is not None else ideal_end
        is_silence = best is not None

        chunks.append(
            ChunkPlan(
                index=index,
                start_secs=start,
                end_secs=end,
                is_silence_boundary=is_silence,
            )
        )
        start = end
        index += 1

    return chunks


def _find_nearest_silence(
    ideal: float,
    tolerance: float,
    silence_points: list[float],
) -> float | None:
    """Find the silence point closest to `ideal` within `tolerance`."""
    best: float | None = None
    best_dist = tolerance

    for sp in silence_points:
        if sp < ideal - tolerance:
            continue
        if sp > ideal + tolerance:
            break
        dist = abs(sp - ideal)
        if dist < best_dist:
            best = sp
            best_dist = dist

    return best
