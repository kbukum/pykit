# pykit-llm

LLM provider abstractions with streaming support and an OpenAI-compatible implementation.

## Installation

```bash
pip install pykit-llm
# or
uv add pykit-llm
```

## Quick Start

```python
import asyncio
from pykit_llm import (
    LLMConfig, CompletionRequest, Message, Role,
)
from pykit_llm.openai import OpenAIProvider

config = LLMConfig(
    base_url="https://api.openai.com/v1",
    api_key="sk-...",
    model="gpt-4o",
    timeout=120.0,
)
provider = OpenAIProvider(config)

async def main():
    # Non-streaming completion
    request = CompletionRequest(
        messages=[
            Message(role=Role.SYSTEM, content="You are a helpful assistant."),
            Message(role=Role.USER, content="What is Python?"),
        ],
        temperature=0.7,
    )
    response = await provider.complete(request)
    print(response.content)
    print(f"Tokens: {response.usage.total_tokens}")

    # Streaming
    request.stream = True
    async for chunk in provider.stream(request):
        print(chunk.content, end="", flush=True)

    await provider.close()

asyncio.run(main())
```

## Key Components

- **LLMProvider** — Runtime-checkable protocol: `async complete(request) -> CompletionResponse` and `async stream(request) -> AsyncIterator[StreamChunk]`
- **OpenAIProvider** — OpenAI-compatible implementation supporting any `/v1/chat/completions` endpoint (OpenAI, Azure, vLLM, llama.cpp); handles SSE stream parsing
- **LLMConfig** — Configuration: `provider`, `base_url`, `api_key`, `model`, `timeout`, `max_retries`
- **CompletionRequest** — Request with `messages`, `model`, `temperature`, `max_tokens`, `stream`, `stop`, `extra`
- **CompletionResponse** — Response with `content`, `model`, `usage`, `finish_reason`
- **StreamChunk** — Streaming chunk with `content`, `done`, `usage`
- **Message** — Chat message with `role`, `content`, optional `name`
- **Role** — StrEnum: `SYSTEM`, `USER`, `ASSISTANT`, `TOOL`
- **Usage** — Token usage: `prompt_tokens`, `completion_tokens`, `total_tokens`
- **LLMError** — Extends `AppError` with `LLMErrorCode` classification and `retryable` flag; factory functions: `auth_error()`, `rate_limit_error()`, `server_error()`, `stream_error()`

## Dependencies

- `httpx` — Async HTTP client
- `pykit-errors` — Base error types

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
