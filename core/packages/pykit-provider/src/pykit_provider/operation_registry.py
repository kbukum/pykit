"""Provider registry — resolve providers by operation ID and tier."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeVar

from pykit_errors import AppError

T = TypeVar("T")


@dataclass
class Binding[T]:
    """Binds an operation ID to a provider with priority and tier access.

    Attributes:
        operation_id: Unique identifier for the operation.
        provider: The provider instance to handle this operation.
        tiers: Allowed tiers. Empty list means all tiers are allowed.
        priority: Lower values are preferred when resolving.
    """

    operation_id: str
    provider: T
    tiers: list[str] = field(default_factory=list)
    priority: int = 0


class Registry[T]:
    """Resolves providers for operations based on tier and priority.

    Resolution order:
        1. Filter bindings by ``operation_id``.
        2. Filter by ``tier`` (bindings with empty ``tiers`` match all).
        3. Sort by ``priority`` ascending (lower = preferred).
        4. Return the first match.

    Raises :class:`AppError` with ``NOT_FOUND`` if no binding matches.
    """

    def __init__(self) -> None:
        self._bindings: dict[str, list[Binding[T]]] = {}

    def bind(self, binding: Binding[T]) -> None:
        """Register a provider binding for an operation.

        Args:
            binding: The operation binding to register.
        """
        self._bindings.setdefault(binding.operation_id, []).append(binding)

    def resolve(self, operation_id: str, tier: str = "") -> T:
        """Resolve the best provider for an operation and tier.

        Args:
            operation_id: The operation to resolve.
            tier: The access tier. Empty string matches bindings with no tier restriction.

        Returns:
            The provider from the highest-priority matching binding.

        Raises:
            AppError: If no binding matches the operation and tier.
        """
        candidates = self._bindings.get(operation_id, [])
        matched = [b for b in candidates if not b.tiers or tier in b.tiers]
        if not matched:
            raise AppError.not_found("operation_binding", operation_id).with_details({"tier": tier})
        matched.sort(key=lambda b: b.priority)
        return matched[0].provider

    def list_bindings(self, operation_id: str) -> list[Binding[T]]:
        """List all bindings registered for an operation.

        Args:
            operation_id: The operation to look up.

        Returns:
            List of bindings, sorted by priority ascending.
        """
        bindings = list(self._bindings.get(operation_id, []))
        bindings.sort(key=lambda b: b.priority)
        return bindings
