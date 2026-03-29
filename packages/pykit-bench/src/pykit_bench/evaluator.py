"""Evaluator protocol and adapters for bench.

An Evaluator is a RequestResponse provider that takes raw bytes input
and produces a Prediction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from pykit_bench.types import Prediction

L = TypeVar("L")


@runtime_checkable
class Evaluator(Protocol[L]):
    """An evaluator that produces predictions from raw input bytes.

    Mirrors gokit's ``bench.Evaluator[L]``.
    """

    @property
    def name(self) -> str:
        """Return the evaluator's unique name."""
        ...

    async def is_available(self) -> bool:
        """Check if the evaluator is ready."""
        ...

    async def evaluate(self, input: bytes) -> Prediction[L]:
        """Execute the evaluator on raw input and return a prediction."""
        ...


class EvaluatorFunc[L]:
    """Wraps an async callable as an Evaluator.

    Example::

        async def classify(data: bytes) -> Prediction[str]:
            return Prediction(label="positive", score=0.95)

        evaluator = EvaluatorFunc("my-model", classify)
        result = await evaluator.evaluate(b"some data")
    """

    def __init__(
        self,
        name: str,
        func: Callable[[bytes], Awaitable[Prediction[L]]],
    ) -> None:
        self._name = name
        self._func = func

    @property
    def name(self) -> str:
        return self._name

    async def is_available(self) -> bool:
        return True

    async def evaluate(self, input: bytes) -> Prediction[L]:
        return await self._func(input)


class FromProvider[L]:
    """Adapts any RequestResponse provider into an Evaluator.

    Uses conversion functions to map between the provider's I/O types
    and the bench bytes/Prediction types.

    Example::

        evaluator = FromProvider(
            provider=my_grpc_client,
            to_input=lambda raw: MyRequest(data=raw),
            to_prediction=lambda resp: Prediction(label=resp.label, score=resp.score),
        )
    """

    def __init__(
        self,
        provider: object,
        to_input: Callable[[bytes], object],
        to_prediction: Callable[[object], Prediction[L]],
    ) -> None:
        self._provider = provider
        self._to_input = to_input
        self._to_prediction = to_prediction

    @property
    def name(self) -> str:
        return self._provider.name  # type: ignore[attr-defined]

    async def is_available(self) -> bool:
        return await self._provider.is_available()  # type: ignore[attr-defined]

    async def evaluate(self, input: bytes) -> Prediction[L]:
        converted = self._to_input(input)
        result = await self._provider.execute(converted)  # type: ignore[attr-defined]
        return self._to_prediction(result)
