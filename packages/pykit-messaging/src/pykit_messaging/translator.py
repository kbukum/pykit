"""Message translation protocols and implementations."""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from pykit_messaging.types import JsonValue
from pykit_util import JsonCodec

T = TypeVar("T")
D = TypeVar("D")


@runtime_checkable
class MessageTranslator(Protocol[T, D]):
    """Translates messages between wire format and domain types.

    Type Parameters:
        T: Wire format type (e.g. bytes).
        D: Domain type (e.g. dict).
    """

    def serialize(self, domain: D) -> T:
        """Serialize a domain object to wire format.

        Args:
            domain: The domain object to serialize.

        Returns:
            The serialized wire-format representation.
        """
        ...

    def deserialize(self, raw: T) -> D:
        """Deserialize wire-format data to a domain object.

        Args:
            raw: The raw wire-format data.

        Returns:
            The deserialized domain object.
        """
        ...


class JsonTranslator:
    """JSON translator for bytes ↔ dict.

    Serializes Python dicts to JSON bytes and deserializes JSON bytes back to dicts.
    """

    def __init__(self, codec: JsonCodec[dict[str, JsonValue]] | None = None) -> None:
        self._codec = codec or JsonCodec()

    def serialize(self, domain: dict[str, JsonValue]) -> bytes:
        """Serialize a dict to JSON bytes.

        Args:
            domain: The dictionary to serialize.

        Returns:
            UTF-8 encoded JSON bytes.
        """
        return self._codec.encode(domain)

    def deserialize(self, raw: bytes) -> dict[str, JsonValue]:
        """Deserialize JSON bytes to a dict.

        Args:
            raw: UTF-8 encoded JSON bytes.

        Returns:
            The deserialized dictionary.
        """
        return self._codec.decode(raw)
