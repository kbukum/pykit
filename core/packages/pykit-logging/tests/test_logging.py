"""Tests for pykit.logging."""

from __future__ import annotations

import asyncio
import io
import json
import re
import sys
from contextvars import copy_context

import structlog

from pykit_logging.setup import (
    add_correlation_id,
    correlation_id_var,
    get_logger,
    new_correlation_id,
    set_correlation_id,
    setup_logging,
)


class TestLogging:
    def test_setup_logging_console(self) -> None:
        setup_logging(level="DEBUG", log_format="console", service_name="test")
        logger = get_logger("test")
        assert logger is not None

    def test_setup_logging_json(self) -> None:
        setup_logging(level="INFO", log_format="json", service_name="test")
        logger = get_logger("test")
        assert logger is not None

    def test_setup_logging_auto(self) -> None:
        setup_logging(level="INFO", log_format="auto")
        logger = get_logger("test")
        assert logger is not None

    def test_correlation_id(self) -> None:
        cid = set_correlation_id("test-123")
        assert cid == "test-123"
        assert correlation_id_var.get() == "test-123"

    def test_correlation_id_auto(self) -> None:
        cid = set_correlation_id()
        assert len(cid) > 0
        assert correlation_id_var.get() == cid

    def test_new_correlation_id(self) -> None:
        cid1 = new_correlation_id()
        cid2 = new_correlation_id()
        assert cid1 != cid2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _json_logger(monkeypatch, *, level="DEBUG", service_name="test-svc"):
    """Configure JSON logging writing to a StringIO buffer. Returns (logger, buf)."""
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    setup_logging(level=level, log_format="json", service_name=service_name)
    logger = get_logger(f"t-{id(buf)}")
    return logger, buf


def _parse_json(buf):
    """Parse the first JSON line from a StringIO buffer."""
    return json.loads(buf.getvalue().strip().splitlines()[0])


# ---------------------------------------------------------------------------
# configure_logging / setup_logging
# ---------------------------------------------------------------------------


class TestSetupLoggingConfiguration:
    """Tests for setup_logging() with various configurations."""

    def test_json_format_produces_valid_json(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch)
        logger.info("json test")
        data = _parse_json(buf)
        assert data["event"] == "json test"

    def test_json_format_contains_log_level(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch)
        logger.warning("warn msg")
        assert _parse_json(buf)["level"] == "warning"

    def test_json_format_contains_timestamp(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch)
        logger.info("ts test")
        assert "timestamp" in _parse_json(buf)

    def test_console_format_contains_message(self, monkeypatch) -> None:
        buf = io.StringIO()
        monkeypatch.setattr(sys, "stderr", buf)
        setup_logging(level="DEBUG", log_format="console", service_name="test-svc")
        get_logger("console-test").info("console test msg")
        assert "console test msg" in buf.getvalue()

    def test_auto_format_defaults_to_console(self, monkeypatch) -> None:
        buf = io.StringIO()
        buf.isatty = lambda: True  # type: ignore[assignment]
        monkeypatch.setattr(sys, "stderr", buf)
        setup_logging(level="DEBUG", log_format="auto", service_name="test-svc")
        get_logger("auto-test").info("auto msg")
        output = buf.getvalue()
        assert "auto msg" in output
        # auto with TTY should not produce JSON
        with __import__("contextlib").suppress(json.JSONDecodeError):
            json.loads(output.strip())
            raise AssertionError("auto format should resolve to console when TTY")  # pragma: no cover

    def test_auto_format_resolves_to_json_without_tty(self, monkeypatch) -> None:
        buf = io.StringIO()
        buf.isatty = lambda: False  # type: ignore[assignment]
        monkeypatch.setattr(sys, "stderr", buf)
        setup_logging(level="DEBUG", log_format="auto", service_name="test-svc")
        get_logger("auto-test").info("auto json msg")
        output = buf.getvalue().strip()
        # auto without TTY should produce JSON
        parsed = json.loads(output)
        assert parsed["event"] == "auto json msg"

    def test_log_level_debug(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch, level="DEBUG")
        logger.debug("dbg")
        assert "dbg" in buf.getvalue()

    def test_log_level_info(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch, level="INFO")
        logger.info("inf")
        assert "inf" in buf.getvalue()

    def test_log_level_warning(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch, level="WARNING")
        logger.warning("wrn")
        assert "wrn" in buf.getvalue()

    def test_log_level_error(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch, level="ERROR")
        logger.error("err")
        assert "err" in buf.getvalue()

    def test_all_parameters(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch, level="DEBUG", service_name="full-svc")
        logger.info("full params")
        assert _parse_json(buf)["event"] == "full params"

    def test_minimal_parameters_defaults(self, monkeypatch) -> None:
        buf = io.StringIO()
        monkeypatch.setattr(sys, "stderr", buf)
        setup_logging()  # defaults: level=INFO, log_format=auto, service_name=pykit
        get_logger("minimal-defaults").info("default msg")
        assert "default msg" in buf.getvalue()


# ---------------------------------------------------------------------------
# get_logger
# ---------------------------------------------------------------------------


class TestGetLoggerDetailed:
    """Detailed tests for get_logger()."""

    def test_returns_logger_instance(self) -> None:
        setup_logging(level="DEBUG", log_format="console")
        assert get_logger("instance-test") is not None

    def test_logger_has_standard_methods(self) -> None:
        setup_logging(level="DEBUG", log_format="console")
        logger = get_logger("methods-test")
        for method in ("debug", "info", "warning", "error", "critical"):
            assert callable(getattr(logger, method, None)), f"missing {method}"

    def test_logger_with_no_name(self) -> None:
        setup_logging(level="DEBUG", log_format="console")
        assert get_logger() is not None

    def test_logger_with_none_name(self) -> None:
        setup_logging(level="DEBUG", log_format="console")
        assert get_logger(None) is not None

    def test_logger_respects_configured_level(self, monkeypatch) -> None:
        buf = io.StringIO()
        monkeypatch.setattr(sys, "stderr", buf)
        setup_logging(level="WARNING", log_format="json")
        get_logger("level-respect").info("should be hidden")
        assert buf.getvalue() == ""


# ---------------------------------------------------------------------------
# Correlation ID
# ---------------------------------------------------------------------------


class TestCorrelationIdManagement:
    """Tests for correlation ID management."""

    def setup_method(self) -> None:
        correlation_id_var.set("")

    def test_set_stores_value(self) -> None:
        set_correlation_id("abc-123")
        assert correlation_id_var.get() == "abc-123"

    def test_set_returns_value(self) -> None:
        assert set_correlation_id("xyz-789") == "xyz-789"

    def test_get_retrieves_value(self) -> None:
        correlation_id_var.set("direct-set")
        assert correlation_id_var.get() == "direct-set"

    def test_default_value_when_not_set(self) -> None:
        assert correlation_id_var.get("") == ""

    def test_default_value_via_default_kwarg(self) -> None:
        # ContextVar was created with default=""
        correlation_id_var.set("")
        assert correlation_id_var.get() == ""

    def test_clear_correlation_id(self) -> None:
        set_correlation_id("will-be-cleared")
        correlation_id_var.set("")
        assert correlation_id_var.get() == ""

    def test_overwrite_correlation_id(self) -> None:
        set_correlation_id("first")
        set_correlation_id("second")
        assert correlation_id_var.get() == "second"

    def test_auto_generate_when_none(self) -> None:
        cid = set_correlation_id()
        assert len(cid) == 36  # UUID4 format: 8-4-4-4-12

    def test_auto_generate_produces_uuid4(self) -> None:
        cid = set_correlation_id()
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
            cid,
        )

    def test_auto_generate_unique(self) -> None:
        cid1 = set_correlation_id()
        cid2 = set_correlation_id()
        assert cid1 != cid2

    def test_new_correlation_id_uuid4_format(self) -> None:
        cid = new_correlation_id()
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
            cid,
        )

    def test_correlation_id_appears_in_json_output(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch)
        set_correlation_id("trace-001")
        logger.info("traced msg")
        assert _parse_json(buf)["correlation_id"] == "trace-001"

    def test_no_correlation_id_field_when_empty(self, monkeypatch) -> None:
        correlation_id_var.set("")
        logger, buf = _json_logger(monkeypatch)
        logger.info("no trace msg")
        assert "correlation_id" not in _parse_json(buf)


# ---------------------------------------------------------------------------
# add_correlation_id processor (unit)
# ---------------------------------------------------------------------------


class TestAddCorrelationIdProcessor:
    """Unit tests for the add_correlation_id structlog processor."""

    def setup_method(self) -> None:
        correlation_id_var.set("")

    def test_adds_id_when_set(self) -> None:
        correlation_id_var.set("proc-123")
        result = add_correlation_id(None, "info", {"event": "test"})
        assert result["correlation_id"] == "proc-123"

    def test_skips_when_empty(self) -> None:
        result = add_correlation_id(None, "info", {"event": "test"})
        assert "correlation_id" not in result

    def test_preserves_existing_fields(self) -> None:
        correlation_id_var.set("proc-456")
        result = add_correlation_id(None, "info", {"event": "test", "extra": "data"})
        assert result["extra"] == "data"
        assert result["event"] == "test"
        assert result["correlation_id"] == "proc-456"

    def test_returns_event_dict(self) -> None:
        event_dict = {"event": "test"}
        result = add_correlation_id(None, "info", event_dict)
        assert result is event_dict


# ---------------------------------------------------------------------------
# Log level filtering
# ---------------------------------------------------------------------------


class TestLogLevelFiltering:
    """Tests for log level filtering behaviour."""

    def test_debug_visible_at_debug(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch, level="DEBUG")
        logger.debug("debug visible")
        assert "debug visible" in buf.getvalue()

    def test_debug_hidden_at_info(self, monkeypatch) -> None:
        buf = io.StringIO()
        monkeypatch.setattr(sys, "stderr", buf)
        setup_logging(level="INFO", log_format="json")
        get_logger("filt-dbg-info").debug("debug hidden")
        assert buf.getvalue() == ""

    def test_info_hidden_at_warning(self, monkeypatch) -> None:
        buf = io.StringIO()
        monkeypatch.setattr(sys, "stderr", buf)
        setup_logging(level="WARNING", log_format="json")
        get_logger("filt-info-warn").info("info hidden")
        assert buf.getvalue() == ""

    def test_warning_hidden_at_error(self, monkeypatch) -> None:
        buf = io.StringIO()
        monkeypatch.setattr(sys, "stderr", buf)
        setup_logging(level="ERROR", log_format="json")
        get_logger("filt-warn-err").warning("warn hidden")
        assert buf.getvalue() == ""

    def test_error_visible_at_error(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch, level="ERROR")
        logger.error("error visible")
        assert "error visible" in buf.getvalue()

    def test_error_visible_at_debug(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch, level="DEBUG")
        logger.error("error always visible")
        assert "error always visible" in buf.getvalue()

    def test_level_change_after_reconfigure(self, monkeypatch) -> None:
        buf = io.StringIO()
        monkeypatch.setattr(sys, "stderr", buf)
        setup_logging(level="INFO", log_format="json")
        get_logger("reconf-before").debug("hidden")
        assert buf.getvalue() == ""
        # Reconfigure to DEBUG
        setup_logging(level="DEBUG", log_format="json")
        get_logger("reconf-after").debug("now visible")
        assert "now visible" in buf.getvalue()


# ---------------------------------------------------------------------------
# JSON output field verification
# ---------------------------------------------------------------------------


class TestJsonOutputFields:
    """Verify JSON output structure and fields."""

    def test_event_field(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch)
        logger.info("my event")
        assert _parse_json(buf)["event"] == "my event"

    def test_log_level_info(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch)
        logger.info("x")
        assert _parse_json(buf)["level"] == "info"

    def test_log_level_debug(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch)
        logger.debug("x")
        assert _parse_json(buf)["level"] == "debug"

    def test_log_level_warning(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch)
        logger.warning("x")
        assert _parse_json(buf)["level"] == "warning"

    def test_log_level_error(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch)
        logger.error("x")
        assert _parse_json(buf)["level"] == "error"

    def test_timestamp_iso_format(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch)
        logger.info("x")
        ts = _parse_json(buf)["timestamp"]
        assert "T" in ts  # ISO 8601

    def test_extra_keyword_fields(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch)
        logger.info("with extras", user_id="u123", action="login")
        data = _parse_json(buf)
        assert data["user_id"] == "u123"
        assert data["action"] == "login"

    def test_numeric_extra_fields(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch)
        logger.info("nums", count=42, ratio=3.14)
        data = _parse_json(buf)
        assert data["count"] == 42
        assert data["ratio"] == 3.14

    def test_none_extra_field(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch)
        logger.info("none val", value=None)
        assert _parse_json(buf)["value"] is None

    def test_nested_dict_extra_field(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch)
        logger.info("nested", metadata={"key": "val", "num": 1})
        assert _parse_json(buf)["metadata"] == {"key": "val", "num": 1}


# ---------------------------------------------------------------------------
# Async safety (contextvars)
# ---------------------------------------------------------------------------


class TestAsyncSafety:
    """Tests for async context safety using contextvars."""

    def setup_method(self) -> None:
        correlation_id_var.set("")

    def test_correlation_id_survives_await(self) -> None:
        async def run():
            set_correlation_id("async-123")
            await asyncio.sleep(0)
            return correlation_id_var.get()

        assert asyncio.run(run()) == "async-123"

    def test_concurrent_tasks_have_independent_ids(self) -> None:
        results: dict[str, str] = {}

        async def set_and_read(name: str, cid: str) -> None:
            set_correlation_id(cid)
            await asyncio.sleep(0.01)
            results[name] = correlation_id_var.get()

        async def main():
            t1 = asyncio.create_task(set_and_read("task1", "id-1"))
            t2 = asyncio.create_task(set_and_read("task2", "id-2"))
            await t1
            await t2

        asyncio.run(main())
        assert results["task1"] == "id-1"
        assert results["task2"] == "id-2"

    def test_correlation_id_in_async_json_output(self, monkeypatch) -> None:
        buf = io.StringIO()
        monkeypatch.setattr(sys, "stderr", buf)
        setup_logging(level="DEBUG", log_format="json")

        async def run():
            set_correlation_id("async-trace")
            get_logger("async-log").info("async message")

        asyncio.run(run())
        assert _parse_json(buf)["correlation_id"] == "async-trace"

    def test_context_copy_preserves_id(self) -> None:
        set_correlation_id("parent-ctx")
        ctx = copy_context()
        assert ctx.run(correlation_id_var.get) == "parent-ctx"

    def test_context_copy_mutations_are_independent(self) -> None:
        set_correlation_id("original")
        ctx = copy_context()

        def mutate():
            set_correlation_id("mutated")
            return correlation_id_var.get()

        assert ctx.run(mutate) == "mutated"
        # Original context unchanged
        assert correlation_id_var.get() == "original"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case and boundary tests."""

    def test_empty_message(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch)
        logger.info("")
        assert _parse_json(buf)["event"] == ""

    def test_unicode_message(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch)
        logger.info("日本語テスト 🚀 émojis àccénts")
        event = _parse_json(buf)["event"]
        assert "日本語テスト" in event
        assert "🚀" in event

    def test_very_long_message(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch)
        long_msg = "x" * 10_000
        logger.info(long_msg)
        assert _parse_json(buf)["event"] == long_msg

    def test_special_characters_in_message(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch)
        special = "quotes \"double\" and 'single' & <angle> \\ backslash"
        logger.info(special)
        assert _parse_json(buf)["event"] == special

    def test_newlines_and_tabs_in_message(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch)
        logger.info("line1\nline2\ttab")
        event = _parse_json(buf)["event"]
        assert "line1" in event
        assert "line2" in event

    def test_reconfigure_logging_changes_level(self, monkeypatch) -> None:
        buf = io.StringIO()
        monkeypatch.setattr(sys, "stderr", buf)
        setup_logging(level="ERROR", log_format="json")
        get_logger("reconf-a").info("hidden at error")
        assert buf.getvalue() == ""
        setup_logging(level="DEBUG", log_format="json")
        get_logger("reconf-b").info("visible at debug")
        assert "visible at debug" in buf.getvalue()

    def test_reconfigure_logging_changes_format(self, monkeypatch) -> None:
        buf = io.StringIO()
        monkeypatch.setattr(sys, "stderr", buf)
        # Start with JSON
        setup_logging(level="DEBUG", log_format="json")
        get_logger("fmt-json").info("json msg")
        first_output = buf.getvalue().strip()
        json.loads(first_output)  # should be valid JSON

        # Reconfigure to console
        buf.truncate(0)
        buf.seek(0)
        setup_logging(level="DEBUG", log_format="console")
        get_logger("fmt-console").info("console msg")
        second_output = buf.getvalue().strip()
        assert "console msg" in second_output

    def test_logger_before_configure(self) -> None:
        """Getting a logger before setup_logging should not crash."""
        structlog.reset_defaults()
        logger = get_logger("pre-config")
        assert logger is not None
        # Restore for subsequent tests
        setup_logging(level="DEBUG", log_format="console")

    def test_format_like_braces_in_message(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch)
        logger.info("value is {not_a_format}")
        assert "{not_a_format}" in _parse_json(buf)["event"]

    def test_correlation_id_with_special_chars(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch)
        cid = "req/123:abc@host"
        set_correlation_id(cid)
        logger.info("special cid")
        assert _parse_json(buf)["correlation_id"] == cid
        correlation_id_var.set("")

    def test_multiple_messages_produce_multiple_json_lines(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch)
        logger.info("first")
        logger.info("second")
        lines = [line for line in buf.getvalue().strip().splitlines() if line.strip()]
        assert len(lines) == 2
        assert json.loads(lines[0])["event"] == "first"
        assert json.loads(lines[1])["event"] == "second"

    def test_boolean_extra_field(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch)
        logger.info("bool", success=True, retry=False)
        data = _parse_json(buf)
        assert data["success"] is True
        assert data["retry"] is False

    def test_list_extra_field(self, monkeypatch) -> None:
        logger, buf = _json_logger(monkeypatch)
        logger.info("list", tags=["a", "b", "c"])
        assert _parse_json(buf)["tags"] == ["a", "b", "c"]
