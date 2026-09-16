# pykit-inference-triton

Triton KServe v2 HTTP adapter for `pykit-inference`.

## Installation

```bash
uv add pykit-inference-triton
# or
pip install pykit-inference-triton
```

## Quick start

```python
from pykit_inference import PredictRequest, Tensor, Value, ValueKind
from pykit_inference_triton import TritonInference
from pykit_inference_triton.client import TritonConfig

adapter = TritonInference(TritonConfig(base_url="http://localhost:8000"))

response = await adapter.predict(
    PredictRequest(
        model_name="classifier",
        inputs={
            "features": Value(
                kind=ValueKind.TENSOR,
                tensor=Tensor(dtype="FP32", shape=[1, 2], data=[0.25, 0.75]),
            )
        },
    )
)

assert response.status.value == "success"
await adapter.close()
```

## Registry wiring

Use `register(registry)` when your application builds inference adapters from a `Registry`.

```python
from pykit_inference.registry import Registry
from pykit_inference_triton import register

registry = Registry()
register(registry)

adapter = registry.build("triton", {"base_url": "http://localhost:8000"})
```

## Adapter behavior

- Sends inference requests to `/v2/models/{model_name}/infer`.
- Uses `/v2/health/ready` for readiness checks through `health_check()`.
- Generates a request ID automatically when `PredictRequest.request_id` is missing.
- Supports `TEXT`, `BYTES`, `TENSOR`, and `JSON` inputs.
- Supports Triton tensor dtypes `FP32`, `INT64`, and `BYTES`.

## Configuration highlights

`TritonConfig` includes:

- `base_url` — defaults to `http://localhost:8000`
- `timeout_seconds` — defaults to `30.0`
- `name`, `description`, `network_host`, `network_port`, `network_scheme`, and `scopes` for runtime metadata and policy
