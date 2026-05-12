"""Echo adapter tests."""

from __future__ import annotations

from pykit_inference import Echo, PredictRequest, Registry, Tensor, Value, ValueKind
from pykit_inference.echo import ECHO_KIND, register


async def test_echo_returns_inputs_unchanged() -> None:
    adapter = Echo()
    req = PredictRequest(
        model_name="echo-model",
        model_version="v1",
        inputs={
            "text": Value(kind=ValueKind.TEXT, text="hello"),
            "tensor": Value(kind=ValueKind.TENSOR, tensor=Tensor(dtype="FP32", shape=[1], data=[1.0])),
        },
    )

    response = await adapter.predict(req)

    assert response.outputs == req.inputs
    assert response.model.name == "echo-model"
    assert response.model.version == "v1"
    assert response.usage.input_tokens == 0


def test_echo_register() -> None:
    registry = Registry()
    register(registry)

    built = registry.build(ECHO_KIND, {})

    assert isinstance(built, Echo)
