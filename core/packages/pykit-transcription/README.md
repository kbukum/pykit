# pykit-transcription

Plan chunks, run parallel transcription, and merge results through a backend-agnostic API.

## Installation

```bash
pip install pykit-transcription
# or
uv add pykit-transcription
```

## Quick start

```python
from pykit_transcription import ChunkedTranscriber, Language, TranscriptionConfig

config = TranscriptionConfig(language=Language.ENGLISH, chunk_duration_secs=600)
transcriber = ChunkedTranscriber(backend=my_whisper_backend, config=config)
result = await transcriber.transcribe("/path/to/audio.wav")
```

## Core APIs

| Module | Responsibility |
| --- | --- |
| `types` | Core types such as `TranscriptSegment`, `TranscriptResult`, `TranscriptionConfig`, and `Language` |
| `protocol` | `TranscriptionBackend` protocol for pluggable engines |
| `chunking` | `plan_chunks()` and `merge_segments()` helpers |
| `orchestrator` | `ChunkedTranscriber` for parallel execution and progress reporting |

## Notes

- Works with any backend that implements `TranscriptionBackend`.
- `ChunkedTranscriber.transcribe()` supports optional duration, silence-point, and progress-callback inputs.
- `pykit-transcription` depends only on `pykit-errors`.

## See also

- [Main pykit README](../../../README.md)
- [tests/](tests/)
