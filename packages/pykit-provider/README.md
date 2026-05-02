# pykit-provider

Provider protocols for the four async interaction patterns: request-response, streaming, sink, and duplex.

## Installation

```bash
pip install pykit-provider
# or
uv add pykit-provider
```

## Quick Start

```python
from pykit_provider import (
    RequestResponse, Stream, Sink, Duplex,
    BoxIterator, DuplexStream, RequestResponseFunc,
)

# Wrap any async function as a RequestResponse provider
async def classify(text: str) -> str:
    return "positive" if "good" in text else "negative"

provider = RequestResponseFunc("sentiment", classify)
print(provider.name)                        # "sentiment"
print(await provider.is_available())        # True
result = await provider.execute("good day") # "positive"

# Implement Stream for server-stream pattern
class EventStream:
    name = "events"
    async def is_available(self) -> bool: return True
    async def execute(self, topic: str) -> BoxIterator[dict]:
        ...  # return a BoxIterator yielding events
```

## Key Components

- **Provider** — Base protocol with `name` property and `is_available()` method
- **RequestResponse[In, Out]** — Unary request → single response (`execute(input) → output`)
- **Stream[In, Out]** — Single request → multiple responses (`execute(input) → BoxIterator[Out]`)
- **Sink[In]** — Fire-and-forget input with no response (`send(input) → None`)
- **Duplex[In, Out]** — Bidirectional communication (`open() → DuplexStream[In, Out]`)
- **BoxIterator[T]** — Async iterator for pull-based sequential access with `next()` and `close()`
- **DuplexStream[In, Out]** — Bidirectional stream with `send()`, `recv()`, and `close()`
- **RequestResponseFunc[In, Out]** — Convenience wrapper to create a RequestResponse from an async callable

## Dependencies

- `pykit-errors`

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
