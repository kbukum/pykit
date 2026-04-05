"""Message translation protocols and implementations."""

from __future__ import annotations

import json
from typing import Any, Protocol, TypeVar, runtime_checkable

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

    def serialize(self, domain: dict[str, Any]) -> bytes:
        """Serialize a dict to JSON bytes.

        Args:
            domain: The dictionary to serialize.

        Returns:
            UTF-8 encoded JSON bytes.
        """
        return json.dumps(domain, default=str).encode()

    def deserialize(self, raw: bytes) -> dict[str, Any]:
        """Deserialize JSON bytes to a dict.

        Args:
            raw: UTF-8 encoded JSON bytes.

        Returns:
            The deserialized dictionary.
        """
        result: dict[str, Any] = json.loads(raw)
        return result
