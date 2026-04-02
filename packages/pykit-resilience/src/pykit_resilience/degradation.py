"""Graceful degradation manager mirroring gokit/resilience/degradation.go."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pykit_resilience.circuit_breaker import State


class ServiceHealth(StrEnum):
    """Health level of a tracked service."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ServiceStatus:
    """Current status of a tracked service."""

    name: str
    health: ServiceHealth = ServiceHealth.HEALTHY
    last_check: float = 0.0
    last_change: float = 0.0
    error: str = ""


class DegradationManager:
    """Tracks service health and feature flags for graceful degradation.

    Thread-safe via :class:`threading.Lock`.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._services: dict[str, ServiceStatus] = {}
        self._features: dict[str, bool] = {}

    def update_service(
        self,
        name: str,
        health: ServiceHealth,
        error: str = "",
    ) -> None:
        """Set the health status for a named service."""
        with self._lock:
            now = time.monotonic()
            existing = self._services.get(name)

            status = ServiceStatus(
                name=name,
                health=health,
                last_check=now,
                last_change=now,
                error=error,
            )

            if existing is not None and existing.health == health:
                status.last_change = existing.last_change

            self._services[name] = status

    def get_status(self, name: str) -> ServiceStatus:
        """Return the status of a named service.

        Returns a default HEALTHY status if the service is not tracked.
        """
        with self._lock:
            return self._services.get(name, ServiceStatus(name=name))

    def all_statuses(self) -> dict[str, ServiceStatus]:
        """Return a snapshot of all tracked service statuses."""
        with self._lock:
            return dict(self._services)

    def set_feature(self, name: str, enabled: bool) -> None:
        """Enable or disable a feature flag."""
        with self._lock:
            self._features[name] = enabled

    def feature_enabled(self, name: str) -> bool:
        """Return whether a feature flag is enabled.

        Returns False for unknown features.
        """
        with self._lock:
            return self._features.get(name, False)

    def is_healthy(self) -> bool:
        """Return True only if all tracked services are HEALTHY."""
        with self._lock:
            return all(s.health == ServiceHealth.HEALTHY for s in self._services.values())

    def on_circuit_breaker_state_change(self, service_name: str):
        """Return a callback compatible with CircuitBreakerConfig.on_state_change.

        Automatically updates the service health when the circuit breaker
        changes state:

        - CLOSED → HEALTHY
        - HALF_OPEN → DEGRADED
        - OPEN → UNHEALTHY
        """

        def callback(name: str, from_state: State, to_state: State) -> None:
            if to_state == State.CLOSED:
                self.update_service(service_name, ServiceHealth.HEALTHY)
            elif to_state == State.HALF_OPEN:
                self.update_service(service_name, ServiceHealth.DEGRADED)
            elif to_state == State.OPEN:
                self.update_service(service_name, ServiceHealth.UNHEALTHY)

        return callback

    def health_check(self) -> dict[str, Any]:
        """Return aggregate health status as a dict.

        Returns 'healthy' status when all services are healthy,
        'degraded' otherwise. Includes per-service statuses.
        """
        statuses = self.all_statuses()
        healthy = self.is_healthy()

        status = "healthy" if healthy else "degraded"
        services = {
            name: {
                "name": s.name,
                "health": s.health,
                "error": s.error,
            }
            for name, s in statuses.items()
        }

        return {"status": status, "services": services}
