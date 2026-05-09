"""Registry behavior tests."""

from __future__ import annotations

import pytest

from pykit_ai import Model
from pykit_inference import InferenceDescriptor, PredictRequest, PredictResponse, Registry
from pykit_tool import Envelope


class FakeInference:
    def descriptor(self) -> InferenceDescriptor:
        return InferenceDescriptor(
            name="fake", description="fake", serving_protocol="fake", envelope=Envelope()
        )

    async def predict(self, request: PredictRequest) -> PredictResponse:
        return PredictResponse(metadata={"model": request.model_name}, model=Model(name=request.model_name))


def test_register_build_and_kinds() -> None:
    registry = Registry()
    registry.register("fake", lambda _config: FakeInference())

    built = registry.build("fake", {})

    assert isinstance(built, FakeInference)
    assert registry.kinds() == ["fake"]


def test_duplicate_registration_rejected() -> None:
    registry = Registry()
    registry.register("fake", lambda _config: FakeInference())

    with pytest.raises(ValueError, match="already registered"):
        registry.register("fake", lambda _config: FakeInference())


def test_unknown_kind_rejected() -> None:
    registry = Registry()

    with pytest.raises(ValueError, match="unknown inference adapter"):
        registry.build("missing", {})


def test_blank_kind_rejected() -> None:
    registry = Registry()

    with pytest.raises(ValueError, match="kind is required"):
        registry.register(" ", lambda _config: FakeInference())
