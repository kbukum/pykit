"""pykit_provider — Provider protocols for the four interaction patterns."""

from __future__ import annotations

from pykit_provider.base import (
    BoxIterator,
    Duplex,
    DuplexStream,
    Provider,
    RequestResponse,
    Sink,
    StreamProvider,
)
from pykit_provider.func import RequestResponseFunc
from pykit_provider.operation_registry import OperationBinding, OperationRegistry

__all__ = [
    "BoxIterator",
    "Duplex",
    "DuplexStream",
    "OperationBinding",
    "OperationRegistry",
    "Provider",
    "RequestResponse",
    "RequestResponseFunc",
    "Sink",
    "StreamProvider",
]
