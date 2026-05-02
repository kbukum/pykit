# pykit-inference

Triton Inference Server client wrapper with async inference, health checking, and automatic dtype conversion.

## Installation

```bash
pip install pykit-inference
# or
uv add pykit-inference

# With gRPC client support (required for actual inference)
pip install pykit-inference[grpc]
```

## Quick Start

```python
import numpy as np
from pykit_inference import TritonClient

client = TritonClient(url="localhost:8001", verbose=False)
client.connect()

# Check server and model readiness
print(client.is_connected)                          # True
print(client.is_model_ready("text-classifier"))     # True

# Run inference
inputs = {"input_text": np.array([b"hello world"], dtype=np.object_)}
outputs = await client.infer(
    model_name="text-classifier",
    inputs=inputs,
    output_names=["label", "confidence"],
)
print(outputs["label"])       # np.array(["positive"])
print(outputs["confidence"])  # np.array([0.95])

# Health check
healthy = await client.health_check()  # True
```

## Key Components

- **TritonClient** — Wrapper around Triton gRPC client with `connect()`, `is_connected`, `is_model_ready()`, `infer()`, and `health_check()` methods
- Automatic numpy-to-Triton dtype conversion (float32→FP32, int64→INT64, bool→BOOL, etc.)
- Lazy dependency loading — `tritonclient[grpc]` is imported on `connect()`, not at import time

## Dependencies

- Optional: `tritonclient[grpc]` (grpc extra)

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
