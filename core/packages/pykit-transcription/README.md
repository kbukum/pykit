# pykit-transcription

Chunked audio transcription orchestration with parallel processing.

## Overview

Provides types, protocols, and orchestration for splitting audio into chunks,
transcribing them in parallel, and merging the results. Backend-agnostic —
works with any transcription engine that implements the `TranscriptionBackend`
protocol.

## Key Components

| Module | Responsibility |
|--------|---------------|
| `types` | Core types: `TranscriptSegment`, `TranscriptResult`, `TranscriptionConfig`, `Language` |
| `protocol` | `TranscriptionBackend` protocol — interface for transcription engines |
| `chunking` | Audio chunk planning and transcript segment merging |
| `orchestrator` | `ChunkedTranscriber` — parallel transcription with progress reporting |

## Usage

```python
from pykit_transcription import (
    ChunkedTranscriber,
    TranscriptionConfig,
    Language,
)

config = TranscriptionConfig(language=Language.ENGLISH, chunk_duration_secs=600)
transcriber = ChunkedTranscriber(backend=my_whisper_backend, config=config)
result = await transcriber.transcribe("/path/to/audio.wav")
```

## Layer

Specialist layer — depends on `pykit-errors` (Foundation).
