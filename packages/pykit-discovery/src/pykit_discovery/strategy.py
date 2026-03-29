"""Load balancing strategies for service discovery."""

from __future__ import annotations

import random
from typing import Protocol, runtime_checkable

from pykit_discovery.types import ServiceInstance


@runtime_checkable
class LoadBalancer(Protocol):
    """Protocol for selecting a service instance from a list."""

    def select(self, instances: list[ServiceInstance]) -> ServiceInstance: ...


class RoundRobinStrategy:
    """Cycles through instances in order."""

    def __init__(self) -> None:
        self._index = 0

    def select(self, instances: list[ServiceInstance]) -> ServiceInstance:
        if not instances:
            raise ValueError("no instances available")
        instance = instances[self._index % len(instances)]
        self._index += 1
        return instance


class RandomStrategy:
    """Selects a random instance."""

    def select(self, instances: list[ServiceInstance]) -> ServiceInstance:
        if not instances:
            raise ValueError("no instances available")
        return random.choice(instances)
