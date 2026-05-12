"""State-machine tests for the component registry."""

from __future__ import annotations

import pytest

from pykit_component import Health, HealthStatus, Registry, State


class StatefulComponent:
    """Configurable component for lifecycle tests."""

    def __init__(self, name: str, *, fail_starts: int = 0, stop_error: Exception | None = None) -> None:
        self._name = name
        self._remaining_fail_starts = fail_starts
        self._stop_error = stop_error
        self.start_calls = 0
        self.stop_calls = 0

    @property
    def name(self) -> str:
        return self._name

    async def start(self) -> None:
        self.start_calls += 1
        if self._remaining_fail_starts > 0:
            self._remaining_fail_starts -= 1
            raise RuntimeError(f"{self._name} start failed")

    async def stop(self) -> None:
        self.stop_calls += 1
        if self._stop_error is not None:
            raise self._stop_error

    async def health(self) -> Health:
        return Health(name=self._name, status=HealthStatus.HEALTHY)


class TestRegistryState:
    @pytest.mark.asyncio
    async def test_start_all_updates_states(self) -> None:
        registry = Registry()
        component = StatefulComponent("db")
        registry.register(component)

        assert registry.state("db") == State.CREATED

        await registry.start_all()

        assert registry.state("db") == State.RUNNING
        assert str(State.STARTING) == "starting"

    @pytest.mark.asyncio
    async def test_partial_failure_rolls_back_started_components(self) -> None:
        registry = Registry()
        first = StatefulComponent("first")
        second = StatefulComponent("second", fail_starts=1)
        third = StatefulComponent("third")
        registry.register(first)
        registry.register(second)
        registry.register(third)

        with pytest.raises(RuntimeError, match="second start failed"):
            await registry.start_all()

        assert registry.state("first") == State.STOPPED
        assert registry.state("second") == State.FAILED
        assert registry.state("third") == State.CREATED
        assert first.stop_calls == 1
        assert third.start_calls == 0

    @pytest.mark.asyncio
    async def test_stop_all_detailed_collects_all_errors(self) -> None:
        registry = Registry()
        first = StatefulComponent("first", stop_error=RuntimeError("first stop failed"))
        second = StatefulComponent("second", stop_error=RuntimeError("second stop failed"))
        registry.register(first)
        registry.register(second)
        await registry.start_all()

        results = await registry.stop_all_detailed()

        assert [result.name for result in results] == ["second", "first"]
        assert [str(result.error) for result in results if result.error is not None] == [
            "second stop failed",
            "first stop failed",
        ]
        assert registry.state("first") == State.FAILED
        assert registry.state("second") == State.FAILED

    @pytest.mark.asyncio
    async def test_stop_all_raises_exception_group_with_all_errors(self) -> None:
        registry = Registry()
        registry.register(StatefulComponent("first", stop_error=RuntimeError("first stop failed")))
        registry.register(StatefulComponent("second", stop_error=RuntimeError("second stop failed")))
        await registry.start_all()

        with pytest.raises(ExceptionGroup) as exc_info:
            await registry.stop_all()

        assert [str(error) for error in exc_info.value.exceptions] == [
            "second stop failed",
            "first stop failed",
        ]

    @pytest.mark.asyncio
    async def test_restart_from_failed_and_stopped(self) -> None:
        registry = Registry()
        flaky = StatefulComponent("flaky", fail_starts=1)
        stable = StatefulComponent("stable")
        registry.register(flaky)
        registry.register(stable)

        with pytest.raises(RuntimeError, match="flaky start failed"):
            await registry.start_all()

        assert registry.state("flaky") == State.FAILED

        await registry.start_all()
        assert registry.state("flaky") == State.RUNNING
        assert registry.state("stable") == State.RUNNING

        await registry.stop_all()
        assert registry.state("flaky") == State.STOPPED
        assert registry.state("stable") == State.STOPPED

        await registry.start_all()
        assert registry.state("flaky") == State.RUNNING
        assert registry.state("stable") == State.RUNNING
