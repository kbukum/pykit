"""Tests for pykit-transcription — chunking, merging, and orchestrator."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from pykit_transcription import (
    ChunkedTranscriber,
    ChunkPlan,
    Language,
    TranscriptionConfig,
    TranscriptionProgress,
    TranscriptResult,
    TranscriptSegment,
    TranscriptWord,
    merge_segments,
    plan_chunks,
)

# ── Types ────────────────────────────────────────────────────────────────────


class TestLanguage:
    def test_from_known_code(self) -> None:
        assert Language.from_code("en") is Language.ENGLISH
        assert Language.from_code("tr") is Language.TURKISH

    def test_from_unknown_code_falls_back_to_auto(self) -> None:
        assert Language.from_code("xx") is Language.AUTO

    def test_from_code_case_insensitive(self) -> None:
        assert Language.from_code("EN") is Language.ENGLISH
        assert Language.from_code("  fr  ") is Language.FRENCH


class TestTranscriptSegment:
    def test_duration(self) -> None:
        seg = TranscriptSegment(text="hello", start_secs=1.0, end_secs=3.5)
        assert seg.duration_secs == pytest.approx(2.5)

    def test_frozen(self) -> None:
        seg = TranscriptSegment(text="hello", start_secs=0.0, end_secs=1.0)
        with pytest.raises(AttributeError):
            seg.text = "world"  # type: ignore[misc]


class TestTranscriptResult:
    def test_full_text(self) -> None:
        result = TranscriptResult(
            segments=(
                TranscriptSegment(text="hello", start_secs=0.0, end_secs=1.0),
                TranscriptSegment(text="world", start_secs=1.0, end_secs=2.0),
            ),
            language="en",
            duration_secs=2.0,
        )
        assert result.full_text == "hello world"
        assert result.segment_count == 2

    def test_empty_result(self) -> None:
        result = TranscriptResult(segments=(), language="en", duration_secs=0.0)
        assert result.full_text == ""
        assert result.segment_count == 0


class TestChunkPlan:
    def test_duration(self) -> None:
        chunk = ChunkPlan(index=0, start_secs=10.0, end_secs=25.0)
        assert chunk.duration_secs == pytest.approx(15.0)


class TestTranscriptionProgress:
    def test_progress_fraction(self) -> None:
        progress = TranscriptionProgress(total_chunks=10, completed_chunks=3)
        assert progress.progress_fraction == pytest.approx(0.3)

    def test_zero_total_progress(self) -> None:
        progress = TranscriptionProgress(total_chunks=0, completed_chunks=0)
        assert progress.progress_fraction == 0.0


# ── Chunking ─────────────────────────────────────────────────────────────────


class TestPlanChunks:
    def test_short_audio_single_chunk(self) -> None:
        config = TranscriptionConfig(chunk_duration_secs=600)
        chunks = plan_chunks(duration_secs=300.0, config=config)
        assert len(chunks) == 1
        assert chunks[0].start_secs == 0.0
        assert chunks[0].end_secs == 300.0

    def test_zero_duration_empty(self) -> None:
        config = TranscriptionConfig(chunk_duration_secs=600)
        assert plan_chunks(duration_secs=0.0, config=config) == []

    def test_fixed_splitting(self) -> None:
        config = TranscriptionConfig(chunk_duration_secs=600)
        chunks = plan_chunks(duration_secs=1500.0, config=config)
        assert len(chunks) == 3
        assert chunks[0].end_secs == 600.0
        assert chunks[1].start_secs == 600.0
        assert chunks[1].end_secs == 1200.0
        assert chunks[2].start_secs == 1200.0
        assert chunks[2].end_secs == 1500.0

    def test_silence_boundary_splitting(self) -> None:
        config = TranscriptionConfig(chunk_duration_secs=600)
        silence_points = [580.0, 1210.0]
        chunks = plan_chunks(duration_secs=1500.0, config=config, silence_points=silence_points)
        # First chunk should split at 580 (silence near 600)
        assert chunks[0].end_secs == 580.0
        assert chunks[0].is_silence_boundary is True

    def test_silence_boundary_fallback_to_fixed(self) -> None:
        """If no silence point is near the target, use fixed split."""
        config = TranscriptionConfig(chunk_duration_secs=600)
        silence_points = [100.0, 200.0]  # All far from 600
        chunks = plan_chunks(duration_secs=1500.0, config=config, silence_points=silence_points)
        assert chunks[0].end_secs == 600.0
        assert chunks[0].is_silence_boundary is False

    def test_exact_duration_match(self) -> None:
        config = TranscriptionConfig(chunk_duration_secs=600)
        chunks = plan_chunks(duration_secs=600.0, config=config)
        assert len(chunks) == 1


# ── Merging ──────────────────────────────────────────────────────────────────


class TestMergeSegments:
    def test_offset_correction(self) -> None:
        chunk_a = ChunkPlan(index=0, start_secs=0.0, end_secs=10.0)
        chunk_b = ChunkPlan(index=1, start_secs=10.0, end_secs=20.0)

        segs_a = [TranscriptSegment(text="hello", start_secs=0.0, end_secs=5.0)]
        segs_b = [TranscriptSegment(text="world", start_secs=0.0, end_secs=4.0)]

        merged = merge_segments([(chunk_a, segs_a), (chunk_b, segs_b)])
        assert len(merged) == 2
        assert merged[0].text == "hello"
        assert merged[0].start_secs == 0.0
        assert merged[1].text == "world"
        assert merged[1].start_secs == 10.0
        assert merged[1].end_secs == 14.0

    def test_word_level_offset(self) -> None:
        chunk = ChunkPlan(index=0, start_secs=60.0, end_secs=120.0)
        segs = [
            TranscriptSegment(
                text="hi",
                start_secs=0.0,
                end_secs=1.0,
                words=(TranscriptWord(text="hi", start_secs=0.0, end_secs=0.5),),
            )
        ]
        merged = merge_segments([(chunk, segs)])
        assert merged[0].words[0].start_secs == 60.0
        assert merged[0].words[0].end_secs == 60.5

    def test_out_of_order_chunks_sorted(self) -> None:
        chunk_b = ChunkPlan(index=1, start_secs=10.0, end_secs=20.0)
        chunk_a = ChunkPlan(index=0, start_secs=0.0, end_secs=10.0)

        segs_a = [TranscriptSegment(text="first", start_secs=0.0, end_secs=5.0)]
        segs_b = [TranscriptSegment(text="second", start_secs=0.0, end_secs=5.0)]

        # Pass in reverse order — should still sort by index
        merged = merge_segments([(chunk_b, segs_b), (chunk_a, segs_a)])
        assert merged[0].text == "first"
        assert merged[1].text == "second"

    def test_empty_results(self) -> None:
        merged = merge_segments([])
        assert merged == ()


# ── Orchestrator ─────────────────────────────────────────────────────────────


class _FakeBackend:
    """Test backend that returns a single segment per chunk."""

    def __init__(self, fail_chunks: set[int] | None = None) -> None:
        self._fail_chunks = fail_chunks or set()
        self.calls: list[Path] = []

    async def transcribe_chunk(
        self, audio_path: Path, config: TranscriptionConfig
    ) -> list[TranscriptSegment]:
        self.calls.append(audio_path)
        if len(self.calls) in self._fail_chunks:
            raise RuntimeError(f"Simulated failure for call {len(self.calls)}")
        return [
            TranscriptSegment(
                text=f"chunk-{len(self.calls)}",
                start_secs=0.0,
                end_secs=5.0,
                language=config.language.value,
            )
        ]

    async def is_available(self) -> bool:
        return True


class TestChunkedTranscriber:
    def test_short_audio_single_chunk(self) -> None:
        backend = _FakeBackend()
        config = TranscriptionConfig(language=Language.ENGLISH)
        transcriber = ChunkedTranscriber(backend=backend, config=config)
        result = asyncio.run(transcriber.transcribe("/tmp/audio.wav", duration_secs=300.0))
        assert result.segment_count == 1
        assert result.language == "en"
        assert len(backend.calls) == 1

    def test_multi_chunk_parallel(self) -> None:
        backend = _FakeBackend()
        config = TranscriptionConfig(language=Language.TURKISH, chunk_duration_secs=600)
        transcriber = ChunkedTranscriber(backend=backend, config=config)
        result = asyncio.run(transcriber.transcribe("/tmp/audio.wav", duration_secs=1500.0))
        assert result.segment_count == 3
        assert result.language == "tr"
        assert len(backend.calls) == 3

    def test_progress_callback(self) -> None:
        backend = _FakeBackend()
        config = TranscriptionConfig(chunk_duration_secs=300)
        transcriber = ChunkedTranscriber(backend=backend, config=config)
        progress_updates: list[TranscriptionProgress] = []

        def on_progress(p: TranscriptionProgress) -> None:
            # Snapshot the progress values
            progress_updates.append(
                TranscriptionProgress(
                    total_chunks=p.total_chunks,
                    completed_chunks=p.completed_chunks,
                    elapsed_secs=p.elapsed_secs,
                )
            )

        asyncio.run(
            transcriber.transcribe(
                "/tmp/audio.wav",
                duration_secs=600.0,
                on_progress=on_progress,
            )
        )
        assert len(progress_updates) == 2  # 2 chunks
        assert progress_updates[-1].completed_chunks == 2

    def test_zero_duration_empty_result(self) -> None:
        backend = _FakeBackend()
        transcriber = ChunkedTranscriber(backend=backend)
        result = asyncio.run(transcriber.transcribe("/tmp/audio.wav", duration_secs=0.0))
        assert result.segment_count == 0
        assert len(backend.calls) == 0

    def test_partial_failure_returns_successful_chunks(self) -> None:
        # Fail the 2nd call but 1st and 3rd succeed
        backend = _FakeBackend(fail_chunks={2})
        config = TranscriptionConfig(chunk_duration_secs=300)
        transcriber = ChunkedTranscriber(backend=backend, config=config)
        result = asyncio.run(transcriber.transcribe("/tmp/audio.wav", duration_secs=900.0))
        # 3 chunks total, 1 failed → 2 segments
        assert result.segment_count == 2

    def test_all_chunks_fail_raises(self) -> None:
        backend = _FakeBackend(fail_chunks={1, 2, 3})
        config = TranscriptionConfig(chunk_duration_secs=300)
        transcriber = ChunkedTranscriber(backend=backend, config=config)
        with pytest.raises(Exception, match=r"All .* chunks failed"):
            asyncio.run(transcriber.transcribe("/tmp/audio.wav", duration_secs=900.0))

    def test_with_silence_points(self) -> None:
        backend = _FakeBackend()
        config = TranscriptionConfig(language=Language.ENGLISH, chunk_duration_secs=600)
        transcriber = ChunkedTranscriber(backend=backend, config=config)
        result = asyncio.run(
            transcriber.transcribe(
                "/tmp/audio.wav",
                duration_secs=1500.0,
                silence_points=[590.0, 1180.0],
            )
        )
        assert result.segment_count == 3
