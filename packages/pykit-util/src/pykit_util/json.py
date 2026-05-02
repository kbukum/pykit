"""Reusable JSON serialization helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Protocol, TypeVar, cast, runtime_checkable

T = TypeVar("T")


@runtime_checkable
class Codec(Protocol[T]):
    """Codec contract for modules that need pluggable value serialization."""

    def encode(self, value: T) -> bytes:
        """Encode a value to bytes."""
        ...

    def decode(self, raw: bytes | str) -> T:
        """Decode bytes or text into a value."""
        ...


class JsonCodec(Codec[T]):
    """UTF-8 JSON codec with deterministic separators and common type support."""

    def __init__(self, *, stringify_unknown: bool = True) -> None:
        self._stringify_unknown = stringify_unknown

    def encode(self, value: T) -> bytes:
        """Encode a value as UTF-8 JSON bytes."""
        return json.dumps(
            value,
            default=lambda item: _json_default(item, stringify_unknown=self._stringify_unknown),
            separators=(",", ":"),
        ).encode()

    def decode(self, raw: bytes | str) -> T:
        """Decode UTF-8 JSON bytes or text."""
        return cast("T", json.loads(raw))


def _json_default(value: object, *, stringify_unknown: bool) -> object:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if not stringify_unknown:
        raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
    return str(value)
