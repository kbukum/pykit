"""Core types for transcription — segments, results, configuration, and language."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Language(Enum):
    """Supported transcription languages.

    Values are BCP 47 language tags used by transcription models.
    """

    AUTO = "auto"
    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    ITALIAN = "it"
    PORTUGUESE = "pt"
    DUTCH = "nl"
    RUSSIAN = "ru"
    CHINESE = "zh"
    JAPANESE = "ja"
    KOREAN = "ko"
    ARABIC = "ar"
    TURKISH = "tr"
    HINDI = "hi"
    POLISH = "pl"
    SWEDISH = "sv"
    CZECH = "cs"

    @classmethod
    def from_code(cls, code: str) -> Language:
        """Resolve a BCP 47 code to a Language variant.

        Falls back to AUTO for unrecognized codes.
        """
        code = code.strip().lower()
        for member in cls:
            if member.value == code:
                return member
        return cls.AUTO


@dataclass(frozen=True)
class TranscriptionConfig:
    """Configuration for a transcription operation.

    Attributes:
        language: Target language for transcription.
        chunk_duration_secs: Target chunk length in seconds for splitting.
        max_concurrent: Maximum parallel transcription tasks.
        model: Transcription model identifier (backend-specific).
        silence_threshold_db: dB threshold for silence detection chunking.
        min_silence_duration_secs: Minimum silence length to consider as a split point.
    """

    language: Language = Language.AUTO
    chunk_duration_secs: int = 600
    max_concurrent: int = 4
    model: str = "base"
    silence_threshold_db: float = -40.0
    min_silence_duration_secs: float = 0.5


@dataclass(frozen=True)
class TranscriptWord:
    """A single word with its timing within a segment.

    Attributes:
        text: The word text.
        start_secs: Start time in seconds from segment start.
        end_secs: End time in seconds from segment start.
        confidence: Recognition confidence (0.0-1.0).
    """

    text: str
    start_secs: float
    end_secs: float
    confidence: float = 1.0


@dataclass(frozen=True)
class TranscriptSegment:
    """A contiguous segment of transcribed speech.

    Attributes:
        text: The transcribed text.
        start_secs: Start time in seconds from the beginning of the source.
        end_secs: End time in seconds from the beginning of the source.
        language: Detected or specified language for this segment.
        confidence: Average recognition confidence (0.0-1.0).
        words: Optional word-level timing (if the backend supports it).
        speaker: Optional speaker identifier (if diarization is available).
    """

    text: str
    start_secs: float
    end_secs: float
    language: str = ""
    confidence: float = 1.0
    words: tuple[TranscriptWord, ...] = ()
    speaker: str | None = None

    @property
    def duration_secs(self) -> float:
        """Duration of this segment in seconds."""
        return self.end_secs - self.start_secs


@dataclass(frozen=True)
class TranscriptResult:
    """Complete transcription result for a media source.

    Attributes:
        segments: All transcribed segments, ordered by time.
        language: The primary detected/requested language.
        duration_secs: Total audio duration in seconds.
        model: Model identifier used for transcription.
    """

    segments: tuple[TranscriptSegment, ...]
    language: str
    duration_secs: float
    model: str = ""

    @property
    def full_text(self) -> str:
        """Concatenated text from all segments."""
        return " ".join(seg.text for seg in self.segments if seg.text)

    @property
    def segment_count(self) -> int:
        """Number of segments in the result."""
        return len(self.segments)


@dataclass(frozen=True)
class ChunkPlan:
    """A planned audio chunk for parallel transcription.

    Attributes:
        index: Chunk index (zero-based).
        start_secs: Start time in the source audio.
        end_secs: End time in the source audio.
        is_silence_boundary: Whether this chunk starts at a silence point.
    """

    index: int
    start_secs: float
    end_secs: float
    is_silence_boundary: bool = False

    @property
    def duration_secs(self) -> float:
        """Duration of this chunk in seconds."""
        return self.end_secs - self.start_secs


@dataclass
class TranscriptionProgress:
    """Progress report during chunked transcription.

    Attributes:
        total_chunks: Total number of chunks to process.
        completed_chunks: Number of chunks completed so far.
        current_chunk: Index of the chunk currently being processed.
        elapsed_secs: Time elapsed since transcription started.
    """

    total_chunks: int = 0
    completed_chunks: int = 0
    current_chunk: int = 0
    elapsed_secs: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def progress_fraction(self) -> float:
        """Progress as a fraction (0.0-1.0)."""
        if self.total_chunks == 0:
            return 0.0
        return self.completed_chunks / self.total_chunks
