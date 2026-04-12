"""Per-module log level overrides for structured logging."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import structlog

# Canonical ordering so we can compare log severity numerically.
_LEVEL_MAP: dict[str, int] = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "warn": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
    "fatal": logging.CRITICAL,
}


@dataclass(frozen=True)
class ModuleLevelsConfig:
    """Per-module log level overrides.

    Attributes:
        levels: Mapping of module name prefixes to minimum log levels.
                Example: ``{"aiokafka": "CRITICAL", "httpx": "WARNING"}``.
    """

    levels: dict[str, str] = field(default_factory=dict)


def module_levels_processor(
    config: ModuleLevelsConfig,
) -> structlog.types.Processor:
    """Create a structlog processor that enforces per-module log levels.

    The processor inspects the ``logger_name`` (or ``_logger_name``) field
    of each event dict.  If the logger name starts with a configured module
    prefix, the event is dropped when its log level is below the configured
    minimum for that module.

    Prefix matching is greedy — the longest matching prefix wins so that
    ``"aiokafka.consumer"`` can override ``"aiokafka"`` if both are present.

    Args:
        config: Module-level override configuration.

    Returns:
        A structlog processor function.
    """
    # Pre-normalise configured levels to numeric values, sorted longest-prefix-first.
    resolved: list[tuple[str, int]] = sorted(
        ((mod, _LEVEL_MAP.get(lvl.lower(), logging.DEBUG)) for mod, lvl in config.levels.items()),
        key=lambda t: len(t[0]),
        reverse=True,
    )

    def _processor(
        logger: Any,
        method_name: str,
        event_dict: dict[str, Any],
    ) -> dict[str, Any]:
        logger_name: str = event_dict.get("logger_name") or event_dict.get("_logger_name", "")

        if not logger_name or not resolved:
            return event_dict

        for prefix, min_level in resolved:
            if logger_name == prefix or logger_name.startswith(prefix + "."):
                event_level_str: str = event_dict.get("level", method_name).lower()
                event_level = _LEVEL_MAP.get(event_level_str, logging.DEBUG)
                if event_level < min_level:
                    raise structlog.DropEvent
                return event_dict

        return event_dict

    return _processor  # type: ignore[return-value]
