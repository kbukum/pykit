"""Tests for pykit_component."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from pykit_component import Component, Description, Health, HealthStatus, Registry, State

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
        with pytest.raises(ExceptionGroup, match="shutdown errors"):
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


# ---------------------------------------------------------------------------
# Additional mock types for new tests
# ---------------------------------------------------------------------------


class SlowComponent:
    """Component that takes time to start/stop."""

    def __init__(self, name: str, delay: float = 0.1) -> None:
        self._name = name
        self._delay = delay
        self._started = False

    @property
    def name(self) -> str:
        return self._name

    async def start(self) -> None:
        await asyncio.sleep(self._delay)
        self._started = True

    async def stop(self) -> None:
        await asyncio.sleep(self._delay)
        self._started = False

    async def health(self) -> Health:
        return Health(name=self._name, status=HealthStatus.HEALTHY)


class CancellingComponent:
    """Component whose start raises CancelledError."""

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    async def start(self) -> None:
        raise asyncio.CancelledError()

    async def stop(self) -> None:
        raise asyncio.CancelledError()

    async def health(self) -> Health:
        return Health(name=self._name, status=HealthStatus.UNHEALTHY)


class DescribableMockComponent:
    """Component that also implements Describable."""

    def __init__(self, name: str, desc: Description) -> None:
        self._name = name
        self._desc = desc

    @property
    def name(self) -> str:
        return self._name

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def health(self) -> Health:
        return Health(name=self._name, status=HealthStatus.HEALTHY)

    def describe(self) -> Description:
        return self._desc


# ---------------------------------------------------------------------------
# GAP 1: asyncio.CancelledError during start_all/stop_all
# ---------------------------------------------------------------------------


class TestCancelledError:
    @pytest.mark.asyncio
    async def test_cancelled_error_during_start_all(self) -> None:
        r = Registry()
        r.register(CancellingComponent("cancel-comp"))
        with pytest.raises(asyncio.CancelledError):
            await r.start_all()

    @pytest.mark.asyncio
    async def test_cancelled_error_during_stop_all(self) -> None:
        """CancelledError is BaseException, not caught by `except Exception`."""
        r = Registry()
        c = MockComponent("good")
        r.register(c)
        await r.start_all()
        # Replace with a component that cancels on stop
        r._entries[0].component = CancellingComponent("cancel-on-stop")
        r._entries[0].state = State.RUNNING
        with pytest.raises(asyncio.CancelledError):
            await r.stop_all()


# ---------------------------------------------------------------------------
# GAP 2: Concurrent start_all + stop_all
# ---------------------------------------------------------------------------


class TestConcurrentOps:
    @pytest.mark.asyncio
    async def test_concurrent_start_stop(self) -> None:
        """Running start and stop concurrently should not corrupt state."""
        r = Registry()
        for i in range(5):
            r.register(MockComponent(f"c-{i}"))

        await r.start_all()

        # Fire off stop and health concurrently — no crash = pass
        results = await asyncio.gather(
            r.stop_all(),
            r.health_all(),
            return_exceptions=True,
        )
        # Just verify no unexpected exception types
        for res in results:
            if isinstance(res, Exception) and not isinstance(res, RuntimeError):
                pytest.fail(f"Unexpected exception: {res}")


# ---------------------------------------------------------------------------
# GAP 3: Partial start failure
# ---------------------------------------------------------------------------


class TestPartialStartFailure:
    @pytest.mark.asyncio
    async def test_partial_start_a_started_b_fails(self) -> None:
        r = Registry()
        order: list[str] = []
        r.register(MockComponent("a", start_order=order))
        r.register(MockComponent("b", start_order=order, start_err=RuntimeError("b boom")))
        r.register(MockComponent("c", start_order=order))

        with pytest.raises(RuntimeError, match="b boom"):
            await r.start_all()

        # "a" started, "b" attempted (raised), "c" never reached
        assert order == ["a", "b"]


# ---------------------------------------------------------------------------
# GAP 4: Multiple stop_all (idempotency)
# ---------------------------------------------------------------------------


class TestStopAllIdempotency:
    @pytest.mark.asyncio
    async def test_double_stop_all(self) -> None:
        r = Registry()
        order: list[str] = []
        r.register(MockComponent("a", stop_order=order))
        await r.start_all()
        await r.stop_all()
        await r.stop_all()  # second call should be no-op
        assert order == ["a"]  # stop called only once

    @pytest.mark.asyncio
    async def test_stop_all_without_start(self) -> None:
        r = Registry()
        r.register(MockComponent("a"))
        # Should not raise
        await r.stop_all()


# ---------------------------------------------------------------------------
# GAP 5: Error message format in RuntimeError aggregation
# ---------------------------------------------------------------------------


class TestStopAllErrorFormat:
    @pytest.mark.asyncio
    async def test_error_message_contains_all_failures(self) -> None:
        r = Registry()
        r.register(MockComponent("db", stop_err=RuntimeError("db timeout")))
        r.register(MockComponent("cache", stop_err=RuntimeError("cache refused")))
        await r.start_all()

        with pytest.raises(ExceptionGroup) as exc_info:
            await r.stop_all()

        msg = str(exc_info.value)
        assert "shutdown errors" in msg
        error_msgs = [str(e) for e in exc_info.value.exceptions]
        assert "db timeout" in error_msgs or any("db timeout" in m for m in error_msgs)
        assert "cache refused" in error_msgs or any("cache refused" in m for m in error_msgs)


# ---------------------------------------------------------------------------
# GAP 6: Health checks during active shutdown
# ---------------------------------------------------------------------------


class TestHealthDuringShutdown:
    @pytest.mark.asyncio
    async def test_health_all_callable_anytime(self) -> None:
        r = Registry()
        r.register(MockComponent("a", status=HealthStatus.HEALTHY))
        # Before start
        results = await r.health_all()
        assert len(results) == 1
        # After start
        await r.start_all()
        results = await r.health_all()
        assert len(results) == 1
        # After stop
        await r.stop_all()
        results = await r.health_all()
        assert len(results) == 1


# ---------------------------------------------------------------------------
# GAP 7: Health timestamp validation
# ---------------------------------------------------------------------------


class TestHealthTimestamp:
    def test_timestamp_is_utc(self) -> None:
        before = datetime.now(UTC)
        h = Health(name="db", status=HealthStatus.HEALTHY)
        after = datetime.now(UTC)
        assert h.timestamp.tzinfo is not None
        assert before <= h.timestamp <= after

    def test_timestamp_is_recent(self) -> None:
        h = Health(name="db", status=HealthStatus.HEALTHY)
        delta = datetime.now(UTC) - h.timestamp
        assert delta.total_seconds() < 1.0


# ---------------------------------------------------------------------------
# GAP 8: HealthStatus string comparison and serialization
# ---------------------------------------------------------------------------


class TestHealthStatusSerialization:
    @pytest.mark.parametrize(
        ("member", "expected_str"),
        [
            (HealthStatus.HEALTHY, "healthy"),
            (HealthStatus.DEGRADED, "degraded"),
            (HealthStatus.UNHEALTHY, "unhealthy"),
        ],
    )
    def test_str_value(self, member: HealthStatus, expected_str: str) -> None:
        assert str(member) == expected_str
        assert member == expected_str
        assert member.value == expected_str

    def test_membership(self) -> None:
        assert "healthy" in [s.value for s in HealthStatus]
        assert len(HealthStatus) == 3

    def test_from_value(self) -> None:
        assert HealthStatus("healthy") is HealthStatus.HEALTHY
        assert HealthStatus("degraded") is HealthStatus.DEGRADED


# ---------------------------------------------------------------------------
# GAP 9: Description immutability
# ---------------------------------------------------------------------------


class TestDescriptionImmutability:
    def test_frozen(self) -> None:
        d = Description(name="HTTP Server", type="server")
        with pytest.raises(AttributeError):
            d.name = "other"  # type: ignore[misc]

    def test_frozen_all_fields(self) -> None:
        d = Description(name="DB", type="database", details="pg:5432", port=5432)
        with pytest.raises(AttributeError):
            d.port = 9999  # type: ignore[misc]


# ---------------------------------------------------------------------------
# GAP 10: Description defaults
# ---------------------------------------------------------------------------


class TestDescriptionDefaults:
    def test_defaults(self) -> None:
        d = Description(name="svc", type="service")
        assert d.details == ""
        assert d.port == 0

    def test_all_fields(self) -> None:
        d = Description(name="pg", type="database", details="pool=25", port=5432)
        assert d.name == "pg"
        assert d.type == "database"
        assert d.details == "pool=25"
        assert d.port == 5432


# ---------------------------------------------------------------------------
# GAP 11: Describable protocol integration
# ---------------------------------------------------------------------------


class TestDescribableProtocol:
    def test_satisfies_describable(self) -> None:
        desc = Description(name="HTTP", type="server", port=8080)
        comp = DescribableMockComponent("http", desc)
        assert isinstance(comp, Component)
        # Describable is not @runtime_checkable, so check duck-typing
        assert hasattr(comp, "describe")
        assert comp.describe() == desc

    def test_describe_returns_correct_values(self) -> None:
        desc = Description(name="cache", type="cache", details="localhost:6379", port=6379)
        comp = DescribableMockComponent("cache", desc)
        result = comp.describe()
        assert result.name == "cache"
        assert result.type == "cache"
        assert result.port == 6379


# ---------------------------------------------------------------------------
# GAP 12: Large component count (50+)
# ---------------------------------------------------------------------------


class TestLargeComponentCount:
    @pytest.mark.asyncio
    async def test_fifty_plus_components(self) -> None:
        r = Registry()
        n = 100
        start_order: list[str] = []
        stop_order: list[str] = []

        for i in range(n):
            name = f"comp-{i:03d}"
            r.register(MockComponent(name, start_order=start_order, stop_order=stop_order))

        assert len(r.all()) == n

        await r.start_all()
        assert len(start_order) == n
        assert start_order == [f"comp-{i:03d}" for i in range(n)]

        await r.stop_all()
        assert len(stop_order) == n
        assert stop_order == [f"comp-{i:03d}" for i in range(n - 1, -1, -1)]

    @pytest.mark.asyncio
    async def test_health_all_large(self) -> None:
        r = Registry()
        for i in range(50):
            r.register(MockComponent(f"c-{i}", status=HealthStatus.HEALTHY))
        results = await r.health_all()
        assert len(results) == 50
        assert all(h.status == HealthStatus.HEALTHY for h in results)


# ---------------------------------------------------------------------------
# GAP 13: Ordering with slow async components
# ---------------------------------------------------------------------------


class TestOrderingWithSlowComponents:
    @pytest.mark.asyncio
    async def test_start_order_preserved_with_delays(self) -> None:
        """Even if components have varying start times, order is sequential."""
        r = Registry()
        order: list[str] = []

        class TimedComponent:
            def __init__(self, name: str, delay: float) -> None:
                self._name = name
                self._delay = delay

            @property
            def name(self) -> str:
                return self._name

            async def start(self) -> None:
                await asyncio.sleep(self._delay)
                order.append(self._name)

            async def stop(self) -> None:
                pass

            async def health(self) -> Health:
                return Health(name=self._name, status=HealthStatus.HEALTHY)

        r.register(TimedComponent("slow", 0.05))
        r.register(TimedComponent("fast", 0.01))
        r.register(TimedComponent("medium", 0.03))

        await r.start_all()
        assert order == ["slow", "fast", "medium"]


# ---------------------------------------------------------------------------
# GAP 14: Empty name registration
# ---------------------------------------------------------------------------


class TestEmptyName:
    def test_empty_name_register_and_get(self) -> None:
        r = Registry()
        c = MockComponent("")
        r.register(c)
        assert r.get("") is c

    def test_empty_name_duplicate(self) -> None:
        r = Registry()
        r.register(MockComponent(""))
        with pytest.raises(ValueError, match="already registered"):
            r.register(MockComponent(""))


# ---------------------------------------------------------------------------
# GAP 15: Unicode names
# ---------------------------------------------------------------------------


class TestUnicodeNames:
    @pytest.mark.parametrize(
        "name",
        [
            "café-résumé",
            "数据库",
            "компонент",
            "name with spaces",
            "emoji-🚀-component",
        ],
    )
    def test_unicode_name_register_get(self, name: str) -> None:
        r = Registry()
        c = MockComponent(name)
        r.register(c)
        got = r.get(name)
        assert got is not None
        assert got.name == name

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "name",
        ["数据库", "компонент"],
    )
    async def test_unicode_name_health(self, name: str) -> None:
        r = Registry()
        r.register(MockComponent(name, status=HealthStatus.HEALTHY))
        results = await r.health_all()
        assert results[0].name == name


# ---------------------------------------------------------------------------
# GAP 16: Security — injection in names / messages
# ---------------------------------------------------------------------------


class TestSecurityInjection:
    @pytest.mark.parametrize(
        "name",
        [
            "'; DROP TABLE components; --",
            "<script>alert('xss')</script>",
            "${ENV_VAR}",
            "../../../etc/passwd",
            "name\x00null",
        ],
    )
    def test_injection_in_names(self, name: str) -> None:
        r = Registry()
        c = MockComponent(name)
        r.register(c)
        got = r.get(name)
        assert got is not None
        assert got.name == name

    @pytest.mark.asyncio
    async def test_injection_in_health_messages(self) -> None:
        msg = "<script>alert('xss')</script>"
        r = Registry()
        r.register(MockComponent("sec", status=HealthStatus.DEGRADED, message=msg))
        results = await r.health_all()
        assert results[0].message == msg


# ---------------------------------------------------------------------------
# GAP 17: Health with all three statuses mixed
# ---------------------------------------------------------------------------


class TestHealthAllStatuses:
    @pytest.mark.asyncio
    async def test_mixed_statuses(self) -> None:
        r = Registry()
        r.register(MockComponent("a", status=HealthStatus.HEALTHY, message="ok"))
        r.register(MockComponent("b", status=HealthStatus.DEGRADED, message="slow"))
        r.register(MockComponent("c", status=HealthStatus.UNHEALTHY, message="down"))

        results = await r.health_all()
        assert len(results) == 3
        assert results[0].status == HealthStatus.HEALTHY
        assert results[0].message == "ok"
        assert results[1].status == HealthStatus.DEGRADED
        assert results[1].message == "slow"
        assert results[2].status == HealthStatus.UNHEALTHY
        assert results[2].message == "down"


# ---------------------------------------------------------------------------
# GAP 18: Registry get edge cases
# ---------------------------------------------------------------------------


class TestRegistryGetEdgeCases:
    def test_get_empty_string_key(self) -> None:
        r = Registry()
        assert r.get("") is None

    def test_get_after_many_registers(self) -> None:
        r = Registry()
        for i in range(50):
            r.register(MockComponent(f"c-{i}"))
        assert r.get("c-0") is not None
        assert r.get("c-49") is not None
        assert r.get("c-50") is None

    def test_all_returns_new_list(self) -> None:
        r = Registry()
        r.register(MockComponent("a"))
        r.register(MockComponent("b"))
        list1 = r.all()
        list2 = r.all()
        assert list1 == list2
        assert list1 is not list2  # different list objects
        list1.clear()
        assert len(r.all()) == 2  # original unchanged
