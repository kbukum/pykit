# pykit-inference-vllm

vLLM OpenAI-compatible completions adapter for `pykit-inference`.

## Installation

```bash
uv add pykit-inference-vllm
# or
pip install pykit-inference-vllm
```

## Quick start

```python
from pykit_inference import PredictRequest, Value, ValueKind
from pykit_inference_vllm import VLLMConfig, VLLMInference

adapter = VLLMInference(
    VLLMConfig(
        base_url="http://localhost:8000",
        model="default",
    )
)

response = await adapter.predict(
    PredictRequest(
        model_name="default",
        inputs={"prompt": Value(kind=ValueKind.TEXT, text="Hello")},
    )
)

assert response.outputs["text"].text is not None
await adapter.close()
```

## Registry wiring

Use `register(registry)` when your application builds inference adapters from a `Registry`.

```python
from pykit_inference.registry import Registry
from pykit_inference_vllm import register

registry = Registry()
register(registry)

adapter = registry.build("vllm", {"base_url": "http://localhost:8000", "model": "default"})
```

## Adapter behavior

- Sends requests to the OpenAI-compatible `/v1/completions` endpoint.
- Accepts prompt text from `request.inputs["prompt"]` or `request.inputs["text"]`.
- Returns generated text in `response.outputs["text"]`.
- Maps token counts from the server response into `response.usage`.

## Configuration highlights

`VLLMConfig` includes:

- `base_url` — defaults to `http://localhost:8000`
- `model` — defaults to `"default"`
- `max_tokens` — defaults to `256`
- `timeout_seconds` — defaults to `30.0`
- `name`, `description`, `network_host`, `network_port`, `network_scheme`, and `scopes` for runtime metadata and policy
