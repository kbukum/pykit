"""Composable middleware helpers for provider shapes."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from pykit_provider.base import Duplex, RequestResponse, Sink, StreamProvider

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")

type Middleware[InputT, OutputT] = Callable[
    [RequestResponse[InputT, OutputT]], RequestResponse[InputT, OutputT]
]
type SinkMiddleware[InputT] = Callable[[Sink[InputT]], Sink[InputT]]
type StreamMiddleware[InputT, OutputT] = Callable[
    [StreamProvider[InputT, OutputT]], StreamProvider[InputT, OutputT]
]
type DuplexMiddleware[InputT, OutputT] = Callable[[Duplex[InputT, OutputT]], Duplex[InputT, OutputT]]


def chain(*middlewares: Middleware[InputT, OutputT]) -> Middleware[InputT, OutputT]:
    """Compose request/response middleware left-to-right."""

    def combined(inner: RequestResponse[InputT, OutputT]) -> RequestResponse[InputT, OutputT]:
        for middleware in reversed(middlewares):
            inner = middleware(inner)
        return inner

    return combined


def chain_sink(*middlewares: SinkMiddleware[InputT]) -> SinkMiddleware[InputT]:
    """Compose sink middleware left-to-right."""

    def combined(inner: Sink[InputT]) -> Sink[InputT]:
        for middleware in reversed(middlewares):
            inner = middleware(inner)
        return inner

    return combined


def chain_stream(*middlewares: StreamMiddleware[InputT, OutputT]) -> StreamMiddleware[InputT, OutputT]:
    """Compose stream middleware left-to-right."""

    def combined(inner: StreamProvider[InputT, OutputT]) -> StreamProvider[InputT, OutputT]:
        for middleware in reversed(middlewares):
            inner = middleware(inner)
        return inner

    return combined


def chain_duplex(*middlewares: DuplexMiddleware[InputT, OutputT]) -> DuplexMiddleware[InputT, OutputT]:
    """Compose duplex middleware left-to-right."""

    def combined(inner: Duplex[InputT, OutputT]) -> Duplex[InputT, OutputT]:
        for middleware in reversed(middlewares):
            inner = middleware(inner)
        return inner

    return combined
