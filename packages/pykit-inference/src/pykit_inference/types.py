"""Normative model-serving inference surface."""

from __future__ import annotations

from collections.abc import AsyncIterator
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pykit_ai import (
    AnyStreamEvent,
    Error,
    JsonValue,
    MessageStart,
    MessageStop,
    Model,
    Provider,
    ReasoningDelta,
    StreamEvent,
    TextDelta,
    ToolUseDelta,
    Usage,
    UsageDelta,
)
from pykit_tool import Envelope


class ValueKind(StrEnum):
    """Supported logical inference value categories."""

    TEXT = "text"
    BYTES = "bytes"
    TENSOR = "tensor"
    JSON = "json"


class PredictStatus(StrEnum):
    """Prediction response status."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    ERROR = "error"


class Tensor(BaseModel):
    """KServe v2-style tensor value."""

    model_config = ConfigDict(extra="forbid")

    dtype: str
    shape: list[int]
    data: list[float] | list[int] | bytes


class Value(BaseModel):
    """Typed inference input or output value."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    kind: ValueKind
    text: str | None = None
    bytes_: bytes | None = Field(default=None, alias="bytes")
    tensor: Tensor | None = None
    json_: JsonValue | None = Field(default=None, alias="json")

    @model_validator(mode="after")
    def _check_kind_payload(self) -> Value:
        field_map: dict[ValueKind, str] = {
            ValueKind.TEXT: "text",
            ValueKind.BYTES: "bytes_",
            ValueKind.TENSOR: "tensor",
            ValueKind.JSON: "json_",
        }
        required = field_map[self.kind]
        if getattr(self, required) is None:
            msg = f"Value(kind={self.kind.value!r}) requires the '{required.rstrip('_')}' field"
            raise ValueError(msg)
        for other_kind, field_name in field_map.items():
            if other_kind != self.kind and getattr(self, field_name) is not None:
                msg = f"Value(kind={self.kind.value!r}) must not set '{field_name.rstrip('_')}'"
                raise ValueError(msg)
        return self


class PredictRequest(BaseModel):
    """Runtime-neutral model prediction request."""

    model_config = ConfigDict(extra="forbid")

    model_name: str
    model_version: str | None = None
    inputs: dict[str, Value] = Field(default_factory=dict)
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    metadata: dict[str, str] = Field(default_factory=dict)
    request_id: str | None = None
    options: dict[str, JsonValue] = Field(default_factory=dict)


class PredictResponse(BaseModel):
    """Runtime-neutral model prediction response."""

    model_config = ConfigDict(extra="forbid")

    outputs: dict[str, Value] = Field(default_factory=dict)
    usage: Usage = Field(default_factory=Usage)
    metadata: dict[str, str] = Field(default_factory=dict)
    model: Model = Field(default_factory=lambda: Model(name="", provider=Provider.CUSTOM))
    status: PredictStatus = PredictStatus.SUCCESS


class InferenceDescriptor(BaseModel):
    """Adapter capability and executable authority declaration."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    serving_protocol: str
    envelope: Envelope


class ChunkEvent(BaseModel):
    """wire: ``chunk`` — non-text serving stream chunk."""

    model_config = ConfigDict(extra="forbid")

    name: str
    value: Value
    index: int | None = None
    type: str = "chunk"


@runtime_checkable
class Inference(Protocol):
    """Async model-serving inference adapter."""

    def descriptor(self) -> InferenceDescriptor: ...

    async def predict(self, request: PredictRequest) -> PredictResponse: ...


@runtime_checkable
class StreamingInference(Inference, Protocol):
    """Inference adapter that can stream prediction events."""

    def predict_stream(self, request: PredictRequest) -> AsyncIterator[StreamEvent | AnyStreamEvent]: ...


__all__ = [
    "ChunkEvent",
    "TextDelta",
    "Inference",
    "InferenceDescriptor",
    "MessageStop",
    "MessageStart",
    "PredictRequest",
    "PredictResponse",
    "PredictStatus",
    "ReasoningDelta",
    "Error",
    "StreamEvent",
    "StreamingInference",
    "Tensor",
    "ToolUseDelta",
    "Usage",
    "UsageDelta",
    "Value",
    "ValueKind",
]
