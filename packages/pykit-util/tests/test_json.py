"""Tests for JSON codec helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from pykit_util import Codec, JsonCodec


@dataclass
class Sample:
    name: str
    count: int


def test_json_codec_round_trip_dict() -> None:
    codec = JsonCodec[dict[str, object]]()
    encoded = codec.encode({"name": "alpha", "count": 3})
    assert codec.decode(encoded) == {"name": "alpha", "count": 3}


def test_json_codec_handles_common_non_json_types() -> None:
    codec = JsonCodec[dict[str, object]]()
    encoded = codec.encode(
        {
            "created_at": datetime(2024, 1, 1, tzinfo=UTC),
            "sample": Sample(name="alpha", count=3),
        }
    )
    assert codec.decode(encoded) == {
        "created_at": "2024-01-01T00:00:00+00:00",
        "sample": {"name": "alpha", "count": 3},
    }


def test_json_codec_satisfies_codec_protocol() -> None:
    assert isinstance(JsonCodec[dict[str, object]](), Codec)
