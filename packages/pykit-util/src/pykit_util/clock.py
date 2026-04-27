"""Deterministic clock abstraction for testable time-dependent code."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol


class Clock(Protocol):
    """Protocol for clock implementations — enables deterministic testing."""

    def now(self) -> datetime:
        """Return the current UTC time."""
        ...


class SystemClock:
    """Real clock backed by ``datetime.now(UTC)``."""

    def now(self) -> datetime:
        return datetime.now(tz=timezone.utc)


class FakeClock:
    """Deterministic clock for tests. Starts at a fixed time; advance manually."""

    def __init__(self, initial: datetime | None = None) -> None:
        self._now = initial or datetime(2024, 1, 1, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self._now

    def advance(self, **kwargs: int) -> None:
        """Advance time by the given timedelta kwargs (e.g., seconds=30)."""
        self._now += timedelta(**kwargs)

    def set(self, dt: datetime) -> None:
        """Set absolute time."""
        self._now = dt
