"""Tests for the degradation manager."""

from __future__ import annotations

from pykit_resilience.circuit_breaker import State
from pykit_resilience.degradation import (
    DegradationManager,
    ServiceHealth,
    ServiceStatus,
)


class TestDegradationManager:
    def test_initial_healthy(self) -> None:
        dm = DegradationManager()
        assert dm.is_healthy() is True

    def test_update_and_get_status(self) -> None:
        dm = DegradationManager()
        dm.update_service("db", ServiceHealth.HEALTHY)
        status = dm.get_status("db")
        assert status.name == "db"
        assert status.health == ServiceHealth.HEALTHY

    def test_unknown_service_returns_default(self) -> None:
        dm = DegradationManager()
        status = dm.get_status("unknown")
        assert status.name == "unknown"
        assert status.health == ServiceHealth.HEALTHY

    def test_unhealthy_service_makes_manager_unhealthy(self) -> None:
        dm = DegradationManager()
        dm.update_service("db", ServiceHealth.HEALTHY)
        dm.update_service("cache", ServiceHealth.UNHEALTHY)
        assert dm.is_healthy() is False

    def test_degraded_service_makes_manager_not_healthy(self) -> None:
        dm = DegradationManager()
        dm.update_service("api", ServiceHealth.DEGRADED)
        assert dm.is_healthy() is False

    def test_all_healthy_returns_true(self) -> None:
        dm = DegradationManager()
        dm.update_service("db", ServiceHealth.HEALTHY)
        dm.update_service("cache", ServiceHealth.HEALTHY)
        assert dm.is_healthy() is True

    def test_all_statuses(self) -> None:
        dm = DegradationManager()
        dm.update_service("db", ServiceHealth.HEALTHY)
        dm.update_service("cache", ServiceHealth.DEGRADED)
        statuses = dm.all_statuses()
        assert len(statuses) == 2
        assert statuses["db"].health == ServiceHealth.HEALTHY
        assert statuses["cache"].health == ServiceHealth.DEGRADED

    def test_update_preserves_last_change_on_same_health(self) -> None:
        dm = DegradationManager()
        dm.update_service("db", ServiceHealth.HEALTHY)
        first_change = dm.get_status("db").last_change
        dm.update_service("db", ServiceHealth.HEALTHY)
        assert dm.get_status("db").last_change == first_change

    def test_update_changes_last_change_on_new_health(self) -> None:
        dm = DegradationManager()
        dm.update_service("db", ServiceHealth.HEALTHY)
        first_change = dm.get_status("db").last_change
        dm.update_service("db", ServiceHealth.UNHEALTHY)
        assert dm.get_status("db").last_change > first_change

    def test_error_recorded(self) -> None:
        dm = DegradationManager()
        dm.update_service("db", ServiceHealth.UNHEALTHY, error="connection refused")
        status = dm.get_status("db")
        assert status.error == "connection refused"


class TestFeatureFlags:
    def test_default_disabled(self) -> None:
        dm = DegradationManager()
        assert dm.feature_enabled("new-ui") is False

    def test_set_and_get(self) -> None:
        dm = DegradationManager()
        dm.set_feature("new-ui", True)
        assert dm.feature_enabled("new-ui") is True
        dm.set_feature("new-ui", False)
        assert dm.feature_enabled("new-ui") is False


class TestCircuitBreakerIntegration:
    def test_on_circuit_breaker_state_change(self) -> None:
        dm = DegradationManager()
        callback = dm.on_circuit_breaker_state_change("db")

        callback("cb", State.CLOSED, State.OPEN)
        assert dm.get_status("db").health == ServiceHealth.UNHEALTHY

        callback("cb", State.OPEN, State.HALF_OPEN)
        assert dm.get_status("db").health == ServiceHealth.DEGRADED

        callback("cb", State.HALF_OPEN, State.CLOSED)
        assert dm.get_status("db").health == ServiceHealth.HEALTHY


class TestHealthCheck:
    def test_healthy_response(self) -> None:
        dm = DegradationManager()
        dm.update_service("db", ServiceHealth.HEALTHY)
        result = dm.health_check()
        assert result["status"] == "healthy"
        assert "db" in result["services"]

    def test_degraded_response(self) -> None:
        dm = DegradationManager()
        dm.update_service("db", ServiceHealth.UNHEALTHY, error="down")
        result = dm.health_check()
        assert result["status"] == "degraded"
        assert result["services"]["db"]["error"] == "down"
