"""Convenience wrappers for creating providers from callables."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

In = TypeVar("In")
Out = TypeVar("Out")


class RequestResponseFunc[In, Out]:
    """Wraps an async callable as a :class:`RequestResponse` provider.

    Example::

        async def classify(data: bytes) -> str:
            return "positive"

        provider = RequestResponseFunc("my-classifier", classify)
        result = await provider.execute(b"some data")
    """

    def __init__(
        self,
        name: str,
        func: Callable[[In], Awaitable[Out]],
    ) -> None:
        self._name = name
        self._func = func

    @property
    def name(self) -> str:
        return self._name

    async def is_available(self) -> bool:
        return True

    async def execute(self, input: In) -> Out:
        return await self._func(input)
