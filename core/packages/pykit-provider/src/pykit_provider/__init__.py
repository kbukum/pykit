"""pykit_provider — Provider protocols for the four interaction patterns."""

from __future__ import annotations

from pykit_provider.base import (
    BoxIterator,
    Duplex,
    DuplexStream,
    Provider,
    RequestResponse,
    Sink,
    Stream,
)
from pykit_provider.func import RequestResponseFunc
from pykit_provider.middleware import (
    DuplexMiddleware,
    Middleware,
    SinkMiddleware,
    StreamMiddleware,
    chain,
    chain_duplex,
    chain_sink,
    chain_stream,
)
from pykit_provider.operation_registry import Binding, Registry

__all__ = [
    "BoxIterator",
    "Duplex",
    "DuplexMiddleware",
    "DuplexStream",
    "Middleware",
    "Binding",
    "Registry",
    "Provider",
    "RequestResponse",
    "RequestResponseFunc",
    "Sink",
    "SinkMiddleware",
    "Stream",
    "StreamMiddleware",
    "chain",
    "chain_duplex",
    "chain_sink",
    "chain_stream",
]
