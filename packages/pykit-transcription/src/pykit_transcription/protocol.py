"""Transcription backend protocol — interface for transcription engines."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from pykit_transcription.types import TranscriptionConfig, TranscriptSegment


@runtime_checkable
class TranscriptionBackend(Protocol):
    """Protocol for transcription engine implementations.

    Backends handle the actual speech-to-text conversion for a single
    audio chunk. The orchestrator calls ``transcribe_chunk`` for each
    chunk in parallel.

    Example implementations:
        - Local Whisper model (whisper, faster-whisper)
        - Remote API (OpenAI Whisper API, Google Speech-to-Text)
        - Triton Inference Server (via pykit-triton)
    """

    async def transcribe_chunk(
        self,
        audio_path: Path,
        config: TranscriptionConfig,
    ) -> list[TranscriptSegment]:
        """Transcribe a single audio chunk.

        Args:
            audio_path: Path to the audio file (WAV, MP3, FLAC, etc.).
            config: Transcription configuration (language, model, etc.).

        Returns:
            List of transcript segments with timestamps relative to the
            chunk start (0.0).
        """
        ...

    async def is_available(self) -> bool:
        """Check if the transcription backend is ready.

        Returns:
            True if the backend can accept transcription requests.
        """
        ...
