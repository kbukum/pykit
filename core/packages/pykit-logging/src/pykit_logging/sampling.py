"""Rate-based log sampling for structured logging."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

import structlog


@dataclass(frozen=True)
class SamplingConfig:
    """Configuration for log sampling.

    Attributes:
        enabled: Whether sampling is active.
        initial_rate: Number of messages allowed per second per level before throttling.
        thereafter_rate: After the initial burst, allow every Nth message.
    """

    enabled: bool = False
    initial_rate: int = 100
    thereafter_rate: int = 100


class LogSampler:
    """Rate-based log sampler using time-windowed counters.

    For each log level, allows ``initial_rate`` messages per second burst,
    then only passes every ``thereafter_rate``-th message.  Counters are
    reset each second (based on ``time.monotonic``).

    Thread-safe: all counter mutations are protected by a lock.
    """

    def __init__(self, config: SamplingConfig) -> None:
        self._config = config
        self._lock = threading.Lock()
        # Per-level state: (window_start, count)
        self._counters: dict[str, tuple[float, int]] = {}

    def should_log(self, level: str) -> bool:
        """Decide whether a log event at *level* should be emitted.

        Args:
            level: The log level string (e.g. ``"info"``, ``"error"``).

        Returns:
            ``True`` if the message should be emitted, ``False`` if it should
            be dropped.
        """
        if not self._config.enabled:
            return True

        now = time.monotonic()
        with self._lock:
            window_start, count = self._counters.get(level, (now, 0))

            # Reset counters when a new 1-second window starts
            if now - window_start >= 1.0:
                window_start = now
                count = 0

            count += 1
            self._counters[level] = (window_start, count)

            if count <= self._config.initial_rate:
                return True

            overflow = count - self._config.initial_rate
            return overflow % self._config.thereafter_rate == 0


def sampling_processor(config: SamplingConfig | None = None) -> structlog.types.Processor:
    """Create a structlog processor that samples logs by rate.

    When a message is dropped by the sampler, ``structlog.DropEvent`` is raised
    so that structlog silently discards the entry.

    Args:
        config: Sampling configuration. Defaults to ``SamplingConfig()``
                (sampling disabled).

    Returns:
        A structlog processor function.
    """
    cfg = config or SamplingConfig()
    sampler = LogSampler(cfg)

    def _processor(
        logger: Any,
        method_name: str,
        event_dict: dict[str, Any],
    ) -> dict[str, Any]:
        level = event_dict.get("level", method_name)
        if not sampler.should_log(level):
            raise structlog.DropEvent
        return event_dict

    return _processor  # type: ignore[return-value]
