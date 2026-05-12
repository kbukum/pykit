"""Service health tracking for observability."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import StrEnum


class HealthStatus(StrEnum):
    """Health state of a service or component."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass(frozen=True)
class ComponentHealth:
    """Health state of an individual component."""

    name: str
    status: HealthStatus
    message: str = ""


class ServiceHealth:
    """Tracks health status of service components.

    Thread-safe aggregate health monitor. Register components and update their
    status; query overall health at any time.
    """

    def __init__(self, service: str, version: str = "") -> None:
        self._service = service
        self._version = version
        self._components: dict[str, ComponentHealth] = {}
        self._lock = threading.Lock()

    @property
    def service(self) -> str:
        return self._service

    @property
    def version(self) -> str:
        return self._version

    def register(self, name: str) -> None:
        """Register a component for health tracking (initially healthy)."""
        with self._lock:
            self._components[name] = ComponentHealth(name=name, status=HealthStatus.HEALTHY)

    def update(self, name: str, status: HealthStatus, message: str = "") -> None:
        """Update the health status of a registered component."""
        with self._lock:
            self._components[name] = ComponentHealth(name=name, status=status, message=message)

    def is_healthy(self) -> bool:
        """Return True if all components are healthy."""
        with self._lock:
            return all(c.status == HealthStatus.HEALTHY for c in self._components.values())

    def status(self) -> dict[str, ComponentHealth]:
        """Return a snapshot of all component health states."""
        with self._lock:
            return dict(self._components)

    def overall_status(self) -> HealthStatus:
        """Return the worst health status across all components."""
        with self._lock:
            if not self._components:
                return HealthStatus.HEALTHY
            statuses = [c.status for c in self._components.values()]
            if HealthStatus.UNHEALTHY in statuses:
                return HealthStatus.UNHEALTHY
            if HealthStatus.DEGRADED in statuses:
                return HealthStatus.DEGRADED
            return HealthStatus.HEALTHY
