"""Tests for pykit_util clock utilities."""

from datetime import UTC, datetime, timedelta

from pykit_util import FakeClock, SystemClock


class TestSystemClock:
    def test_returns_utc(self) -> None:
        clock = SystemClock()
        now = clock.now()
        diff = abs((datetime.now(tz=UTC) - now).total_seconds())
        assert diff < 2


class TestFakeClock:
    def test_default_start(self) -> None:
        clock = FakeClock()
        assert clock.now() == datetime(2024, 1, 1, tzinfo=UTC)

    def test_custom_initial(self) -> None:
        initial = datetime(2020, 5, 1, 8, 30, tzinfo=UTC)
        clock = FakeClock(initial=initial)
        assert clock.now() == initial

    def test_advance(self) -> None:
        clock = FakeClock()
        clock.advance(seconds=30)
        assert clock.now() == datetime(2024, 1, 1, 0, 0, 30, tzinfo=UTC)

    def test_advance_multiple(self) -> None:
        clock = FakeClock()
        clock.advance(hours=1)
        clock.advance(minutes=30)
        expected = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=1, minutes=30)
        assert clock.now() == expected

    def test_set(self) -> None:
        clock = FakeClock()
        target = datetime(2025, 6, 15, 12, 0, tzinfo=UTC)
        clock.set(target)
        assert clock.now() == target
