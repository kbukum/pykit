"""Tests for embedding types, distance metrics, and aggregation functions."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from pykit_ai import Model
from pykit_ai.vector import cosine_similarity, dot_product, euclidean_distance, max_pooling, mean_pooling
from pykit_embedding.types import (
    Embedding,
    EmbedInput,
    EmbedRequest,
    Image,
    Text,
    Video,
)


def test_embedding_dimensions_validated() -> None:
    e = Embedding(vector=[1.0, 2.0, 3.0], dimensions=3, index=0)
    assert e.dimensions == 3
    with pytest.raises(ValidationError):
        Embedding(vector=[1.0], dimensions=2, index=0)


def test_embed_input_discriminator() -> None:
    adapter = TypeAdapter(EmbedInput)
    assert adapter.validate_python({"type": "text", "text": "hello"}) == Text(text="hello")
    assert adapter.validate_python({"type": "image", "url": "https://example.test/a.png"}) == Image(
        url="https://example.test/a.png"
    )
    assert adapter.validate_python({"type": "video", "data": b"x"}) == Video(data=b"x")


def test_embed_request_options_are_provider_specific() -> None:
    req = EmbedRequest(model=Model(name="m"), inputs=[Text(text="hello")], options={"dimensions": 3})
    assert req.options == {"dimensions": 3}


def test_cosine_similarity() -> None:
    v = [1.0, 2.0, 3.0]
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-6
    assert cosine_similarity([1.0, 2.0], [0.0, 0.0]) == 0.0
    with pytest.raises(ValueError, match="equal dimensions"):
        cosine_similarity([1.0, 2.0], [1.0])


def test_euclidean_distance() -> None:
    assert abs(euclidean_distance([0.0, 0.0], [3.0, 4.0]) - 5.0) < 1e-6
    with pytest.raises(ValueError, match="equal dimensions"):
        euclidean_distance([1.0], [1.0, 2.0])


def test_dot_product() -> None:
    assert abs(dot_product([1.0, 2.0, 3.0], [4.0, 5.0, 6.0]) - 32.0) < 1e-6
    with pytest.raises(ValueError, match="equal dimensions"):
        dot_product([1.0], [1.0, 2.0])


def test_pooling() -> None:
    assert mean_pooling([]) is None
    assert mean_pooling([[1.0, 3.0], [3.0, 1.0]]) == [2.0, 2.0]
    assert max_pooling([]) is None
    assert max_pooling([[1.0, 4.0], [3.0, 2.0]]) == [3.0, 4.0]
    with pytest.raises(ValueError, match="equal dimensions"):
        mean_pooling([[1.0, 2.0], [1.0]])
    with pytest.raises(ValueError, match="equal dimensions"):
        max_pooling([[1.0, 2.0], [1.0]])
