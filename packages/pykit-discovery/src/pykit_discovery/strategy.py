"""Load balancing strategies for service discovery."""

from __future__ import annotations

import random
import threading
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


class LeastConnectionsStrategy:
    """Picks the instance with the fewest in-flight requests."""

    def __init__(self) -> None:
        self._in_flight: dict[str, int] = {}
        self._lock = threading.Lock()

    def select(self, instances: list[ServiceInstance]) -> ServiceInstance:
        """Select the instance with the fewest active connections."""
        if not instances:
            msg = "No instances available"
            raise ValueError(msg)
        with self._lock:
            best = min(instances, key=lambda i: self._in_flight.get(i.id, 0))
            return best

    def acquire(self, instance_id: str) -> None:
        """Increment in-flight count for an instance."""
        with self._lock:
            self._in_flight[instance_id] = self._in_flight.get(instance_id, 0) + 1

    def release(self, instance_id: str) -> None:
        """Decrement in-flight count for an instance."""
        with self._lock:
            count = self._in_flight.get(instance_id, 0)
            if count > 0:
                self._in_flight[instance_id] = count - 1
