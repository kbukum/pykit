"""Tests for pykit_logging.module_levels."""

from __future__ import annotations

from typing import Any

import structlog

from pykit_logging.module_levels import ModuleLevelsConfig, module_levels_processor

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event_dict(**kwargs: Any) -> dict[str, Any]:
    """Build a minimal structlog event_dict for processor tests."""
    return kwargs


# ---------------------------------------------------------------------------
# ModuleLevelsConfig
# ---------------------------------------------------------------------------


class TestModuleLevelsConfig:
    def test_defaults(self) -> None:
        cfg = ModuleLevelsConfig()
        assert cfg.levels == {}

    def test_custom(self) -> None:
        cfg = ModuleLevelsConfig(levels={"aiokafka": "CRITICAL"})
        assert cfg.levels["aiokafka"] == "CRITICAL"


# ---------------------------------------------------------------------------
# Processor: module-specific level override
# ---------------------------------------------------------------------------


class TestModuleLevelsProcessor:
    def test_drops_below_configured_level(self) -> None:
        proc = module_levels_processor(ModuleLevelsConfig(levels={"aiokafka": "CRITICAL"}))
        ed = _make_event_dict(event="reconnecting", level="info", logger_name="aiokafka")
        try:
            proc(None, "info", ed)  # type: ignore[arg-type]
            raised = False
        except structlog.DropEvent:
            raised = True
        assert raised, "Expected DropEvent for level below CRITICAL"

    def test_allows_at_configured_level(self) -> None:
        proc = module_levels_processor(ModuleLevelsConfig(levels={"aiokafka": "WARNING"}))
        ed = _make_event_dict(event="slow", level="warning", logger_name="aiokafka")
        result = proc(None, "warning", ed)  # type: ignore[arg-type]
        assert result["event"] == "slow"

    def test_allows_above_configured_level(self) -> None:
        proc = module_levels_processor(ModuleLevelsConfig(levels={"aiokafka": "WARNING"}))
        ed = _make_event_dict(event="crash", level="error", logger_name="aiokafka")
        result = proc(None, "error", ed)  # type: ignore[arg-type]
        assert result["event"] == "crash"

    def test_prefix_matching(self) -> None:
        """``'aiokafka'`` should match ``'aiokafka.consumer'``."""
        proc = module_levels_processor(ModuleLevelsConfig(levels={"aiokafka": "ERROR"}))
        ed = _make_event_dict(event="poll", level="info", logger_name="aiokafka.consumer")
        try:
            proc(None, "info", ed)  # type: ignore[arg-type]
            raised = False
        except structlog.DropEvent:
            raised = True
        assert raised

    def test_prefix_does_not_match_partial_name(self) -> None:
        """``'aio'`` should NOT match ``'aiokafka'`` — only exact or dot-separated."""
        proc = module_levels_processor(ModuleLevelsConfig(levels={"aio": "CRITICAL"}))
        ed = _make_event_dict(event="ok", level="info", logger_name="aiokafka")
        result = proc(None, "info", ed)  # type: ignore[arg-type]
        assert result["event"] == "ok"

    def test_unmatched_module_passes_through(self) -> None:
        proc = module_levels_processor(ModuleLevelsConfig(levels={"aiokafka": "CRITICAL"}))
        ed = _make_event_dict(event="hello", level="debug", logger_name="myapp.service")
        result = proc(None, "debug", ed)  # type: ignore[arg-type]
        assert result["event"] == "hello"

    def test_no_logger_name_passes_through(self) -> None:
        proc = module_levels_processor(ModuleLevelsConfig(levels={"aiokafka": "CRITICAL"}))
        ed = _make_event_dict(event="anonymous", level="debug")
        result = proc(None, "debug", ed)  # type: ignore[arg-type]
        assert result["event"] == "anonymous"

    def test_empty_config_passes_everything(self) -> None:
        proc = module_levels_processor(ModuleLevelsConfig())
        ed = _make_event_dict(event="msg", level="debug", logger_name="anything")
        result = proc(None, "debug", ed)  # type: ignore[arg-type]
        assert result["event"] == "msg"

    def test_case_insensitive_level(self) -> None:
        """Level strings are normalised case-insensitively."""
        proc = module_levels_processor(ModuleLevelsConfig(levels={"noisy": "Warning"}))
        ed = _make_event_dict(event="low", level="info", logger_name="noisy")
        try:
            proc(None, "info", ed)  # type: ignore[arg-type]
            raised = False
        except structlog.DropEvent:
            raised = True
        assert raised

    def test_longest_prefix_wins(self) -> None:
        """When both ``'aiokafka'`` and ``'aiokafka.consumer'`` are configured,
        the more specific prefix takes precedence."""
        proc = module_levels_processor(
            ModuleLevelsConfig(levels={"aiokafka": "CRITICAL", "aiokafka.consumer": "WARNING"}),
        )
        # ``aiokafka.consumer`` gets the WARNING threshold (not CRITICAL)
        ed = _make_event_dict(event="poll", level="warning", logger_name="aiokafka.consumer")
        result = proc(None, "warning", ed)  # type: ignore[arg-type]
        assert result["event"] == "poll"

    def test_uses_underscore_logger_name(self) -> None:
        """Falls back to ``_logger_name`` when ``logger_name`` is absent."""
        proc = module_levels_processor(ModuleLevelsConfig(levels={"httpx": "ERROR"}))
        ed = _make_event_dict(event="req", level="info", _logger_name="httpx")
        try:
            proc(None, "info", ed)  # type: ignore[arg-type]
            raised = False
        except structlog.DropEvent:
            raised = True
        assert raised
