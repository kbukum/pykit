"""Value and tensor pydantic round-trip tests."""

from __future__ import annotations

from pykit_inference import Tensor, Value, ValueKind


def test_text_value_round_trip() -> None:
    value = Value(kind=ValueKind.TEXT, text="hello")

    restored = Value.model_validate(value.model_dump(by_alias=True))

    assert restored == value


def test_bytes_value_round_trip() -> None:
    value = Value(kind=ValueKind.BYTES, bytes=b"hello")

    dumped = value.model_dump(by_alias=True)
    restored = Value.model_validate(dumped)

    assert dumped["bytes"] == b"hello"
    assert restored.bytes_ == b"hello"


def test_tensor_value_round_trip() -> None:
    value = Value(kind=ValueKind.TENSOR, tensor=Tensor(dtype="FP32", shape=[1, 2], data=[1.0, 2.0]))

    restored = Value.model_validate(value.model_dump(by_alias=True))

    assert restored == value


def test_json_value_round_trip() -> None:
    value = Value(kind=ValueKind.JSON, json={"labels": ["a", "b"], "score": 0.9})

    dumped = value.model_dump(by_alias=True)
    restored = Value.model_validate(dumped)

    assert dumped["json"] == {"labels": ["a", "b"], "score": 0.9}
    assert restored == value
