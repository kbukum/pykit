"""Tests for pykit_component."""

from __future__ import annotations

import pytest

from pykit_component import Component, Health, HealthStatus, Registry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class MockComponent:
    """Minimal Component implementation for testing."""

    def __init__(
        self,
        name: str,
        *,
        start_err: Exception | None = None,
        stop_err: Exception | None = None,
        status: HealthStatus = HealthStatus.HEALTHY,
        message: str = "",
        start_order: list[str] | None = None,
        stop_order: list[str] | None = None,
    ) -> None:
        self._name = name
        self._start_err = start_err
        self._stop_err = stop_err
        self._status = status
        self._message = message
        self._start_order = start_order
        self._stop_order = stop_order

    @property
    def name(self) -> str:
        return self._name

    async def start(self) -> None:
        if self._start_order is not None:
            self._start_order.append(self._name)
        if self._start_err:
            raise self._start_err

    async def stop(self) -> None:
        if self._stop_order is not None:
            self._stop_order.append(self._name)
        if self._stop_err:
            raise self._stop_err

    async def health(self) -> Health:
        return Health(name=self._name, status=self._status, message=self._message)


# ---------------------------------------------------------------------------
# HealthStatus
# ---------------------------------------------------------------------------


class TestHealthStatus:
    def test_values(self) -> None:
        assert HealthStatus.HEALTHY == "healthy"
        assert HealthStatus.DEGRADED == "degraded"
        assert HealthStatus.UNHEALTHY == "unhealthy"

    def test_is_str(self) -> None:
        assert isinstance(HealthStatus.HEALTHY, str)


# ---------------------------------------------------------------------------
# Health dataclass
# ---------------------------------------------------------------------------


class TestHealth:
    def test_defaults(self) -> None:
        h = Health(name="db", status=HealthStatus.HEALTHY)
        assert h.name == "db"
        assert h.status == HealthStatus.HEALTHY
        assert h.message == ""
        assert h.timestamp is not None

    def test_with_message(self) -> None:
        h = Health(name="cache", status=HealthStatus.DEGRADED, message="high latency")
        assert h.message == "high latency"

    def test_frozen(self) -> None:
        h = Health(name="db", status=HealthStatus.HEALTHY)
        with pytest.raises(AttributeError):
            h.name = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Component protocol
# ---------------------------------------------------------------------------


class TestComponentProtocol:
    def test_mock_satisfies_protocol(self) -> None:
        c = MockComponent("db")
        assert isinstance(c, Component)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_register_and_get(self) -> None:
        r = Registry()
        c = MockComponent("db")
        r.register(c)
        assert r.get("db") is c

    def test_get_missing(self) -> None:
        r = Registry()
        assert r.get("missing") is None

    def test_all(self) -> None:
        r = Registry()
        r.register(MockComponent("db"))
        r.register(MockComponent("cache"))
        names = [c.name for c in r.all()]
        assert names == ["db", "cache"]

    def test_duplicate_raises(self) -> None:
        r = Registry()
        r.register(MockComponent("db"))
        with pytest.raises(ValueError, match="already registered"):
            r.register(MockComponent("db"))

    def test_empty_registry(self) -> None:
        r = Registry()
        assert r.all() == []
        assert r.get("x") is None

    @pytest.mark.asyncio
    async def test_start_all_order(self) -> None:
        r = Registry()
        order: list[str] = []
        r.register(MockComponent("db", start_order=order))
        r.register(MockComponent("cache", start_order=order))
        r.register(MockComponent("kafka", start_order=order))
        await r.start_all()
        assert order == ["db", "cache", "kafka"]

    @pytest.mark.asyncio
    async def test_start_all_error(self) -> None:
        r = Registry()
        r.register(MockComponent("db", start_err=RuntimeError("connection refused")))
        with pytest.raises(RuntimeError, match="connection refused"):
            await r.start_all()

    @pytest.mark.asyncio
    async def test_stop_all_reverse_order(self) -> None:
        r = Registry()
        order: list[str] = []
        r.register(MockComponent("db", stop_order=order))
        r.register(MockComponent("cache", stop_order=order))
        r.register(MockComponent("kafka", stop_order=order))
        await r.start_all()
        await r.stop_all()
        assert order == ["kafka", "cache", "db"]

    @pytest.mark.asyncio
    async def test_stop_all_skips_unstarted(self) -> None:
        r = Registry()
        order: list[str] = []
        r.register(MockComponent("db", stop_order=order))
        await r.stop_all()
        assert order == []

    @pytest.mark.asyncio
    async def test_stop_all_with_errors(self) -> None:
        r = Registry()
        r.register(MockComponent("db", stop_err=RuntimeError("stop failed")))
        await r.start_all()
        with pytest.raises(RuntimeError, match="shutdown errors"):
            await r.stop_all()

    @pytest.mark.asyncio
    async def test_health_all(self) -> None:
        r = Registry()
        r.register(MockComponent("db", status=HealthStatus.HEALTHY, message="connected"))
        r.register(MockComponent("cache", status=HealthStatus.UNHEALTHY, message="timeout"))
        results = await r.health_all()
        assert len(results) == 2
        assert results[0].status == HealthStatus.HEALTHY
        assert results[0].message == "connected"
        assert results[1].status == HealthStatus.UNHEALTHY
        assert results[1].message == "timeout"

    @pytest.mark.asyncio
    async def test_health_all_empty(self) -> None:
        r = Registry()
        results = await r.health_all()
        assert results == []
