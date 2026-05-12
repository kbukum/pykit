"""pykit-transcription — Chunked audio transcription with parallel processing."""

__version__ = "0.1.0"

from pykit_transcription.chunking import merge_segments, plan_chunks
from pykit_transcription.orchestrator import ChunkedTranscriber
from pykit_transcription.protocol import TranscriptionBackend
from pykit_transcription.types import (
    ChunkPlan,
    Language,
    TranscriptionConfig,
    TranscriptionProgress,
    TranscriptResult,
    TranscriptSegment,
    TranscriptWord,
)

__all__ = [
    "ChunkPlan",
    "ChunkedTranscriber",
    "Language",
    "TranscriptResult",
    "TranscriptSegment",
    "TranscriptWord",
    "TranscriptionBackend",
    "TranscriptionConfig",
    "TranscriptionProgress",
    "merge_segments",
    "plan_chunks",
]
