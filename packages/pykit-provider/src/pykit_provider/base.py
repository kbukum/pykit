"""Provider protocols — the four interaction patterns."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import AsyncIterator
from typing import Protocol, TypeVar, runtime_checkable

In = TypeVar("In", contravariant=True)
Out = TypeVar("Out", covariant=True)
T = TypeVar("T")


@runtime_checkable
class Provider(Protocol):
    """Base protocol all providers must implement.

    Provides identity (``name``) and health checking (``is_available``).
    """

    @property
    def name(self) -> str:
        """Return the provider's unique name."""
        ...

    async def is_available(self) -> bool:
        """Check if the provider is ready to handle requests."""
        ...


class BoxIterator[T](AsyncIterator[T]):
    """Async iterator providing pull-based sequential access to values.

    Mirrors gokit's ``provider.Iterator[T]``.
    """

    @abstractmethod
    async def next(self) -> T | None:
        """Return the next value, or ``None`` when exhausted."""
        ...

    async def close(self) -> None:
        """Release any resources held by the iterator."""

    def __aiter__(self) -> BoxIterator[T]:
        return self

    async def __anext__(self) -> T:
        val = await self.next()
        if val is None:
            raise StopAsyncIteration
        return val


@runtime_checkable
class RequestResponse(Provider, Protocol[In, Out]):
    """A provider that takes one input and returns one output.

    Covers: gRPC unary, HTTP request/response, subprocess exec, SQL query.
    """

    async def execute(self, input: In) -> Out:
        """Execute a request and return the response."""
        ...


@runtime_checkable
class StreamProvider(Provider, Protocol[In, Out]):
    """A provider that takes one input and returns multiple outputs.

    Covers: gRPC server-stream, subprocess stdout pipe, SSE, chunked HTTP.
    """

    async def execute(self, input: In) -> BoxIterator[Out]:
        """Execute a request and return a stream of results."""
        ...


@runtime_checkable
class Sink(Provider, Protocol[In]):
    """A provider that accepts input with no meaningful output.

    Covers: Kafka produce, webhook, push notification, logging.
    """

    async def send(self, input: In) -> None:
        """Send a value to the sink."""
        ...


class DuplexStream[In, Out]:
    """A bidirectional stream for duplex communication."""

    @abstractmethod
    async def send(self, input: In) -> None:
        """Send a value to the remote end."""
        ...

    @abstractmethod
    async def recv(self) -> Out | None:
        """Receive a value from the remote end. Returns None when closed."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the stream."""
        ...


@runtime_checkable
class Duplex(Provider, Protocol[In, Out]):
    """A provider with bidirectional communication.

    Covers: WebSocket, gRPC bidi-stream, long-running subprocess.
    """

    async def open(self) -> DuplexStream[In, Out]:
        """Open a bidirectional stream."""
        ...
