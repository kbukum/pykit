# pykit-llm

LLM provider abstractions with streaming support.

Vendor-specific implementations live in **pykit-llm-providers**:
- **OpenAI** — OpenAI-compatible provider (OpenAI, Azure, vLLM, llama.cpp)
- **Anthropic** — Anthropic Claude provider
- **Gemini** — Google Gemini provider

## Installation

```bash
pip install pykit-llm
# For vendor implementations:
pip install pykit-llm-providers
```

## Quick Start

```python
import asyncio
from pykit_llm import CompletionRequest, user
from pykit_llm_providers.openai import OpenAIConfig, OpenAIProvider

config = OpenAIConfig(
    api_key="sk-...",
    model="gpt-4o",
)
provider = OpenAIProvider(config)

async def main():
    request = CompletionRequest(messages=[user("What is Python?")])
    response = await provider.complete(request)
    print(response.text())

    # Streaming
    async for chunk in provider.stream(request):
        print(chunk.content, end="", flush=True)

    await provider.close()

asyncio.run(main())
```

## Key Components

- **LLMProvider** — Runtime-checkable protocol: `async complete(request) -> CompletionResponse` and `async stream(request) -> AsyncIterator[StreamChunk]`
- **LLMConfig** — Configuration: `provider`, `base_url`, `api_key`, `model`, `timeout`, `max_retries`
- **CompletionRequest** — Request with `messages`, `model`, `temperature`, `max_tokens`, `stream`, `stop`, `extra`
- **CompletionResponse** — Response with `message`, `model`, `usage`, `stop_reason`
- **StreamChunk** — Streaming chunk with `content`, `done`, `usage`
- **Message** — Discriminated union: `UserMessage | AssistantMessage | ToolResultMessage | SystemMessage`
- **Usage** — Token usage: `prompt_tokens`, `completion_tokens`, `total_tokens`
- **LLMError** — Extends `AppError` with `LLMErrorCode` classification and `retryable` flag

## Dependencies

- `pykit-errors` — Base error types
- `pykit-tool` — Tool definitions

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
