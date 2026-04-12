"""Tests for the OpenTelemetry OTLP log bridge."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from pykit_logging.otlp import (
    _SEVERITY_MAP,
    OTLPConfig,
    OTLPLogBridge,
    _sanitize_attributes,
    otlp_processor,
)

# ---------------------------------------------------------------------------
# Helpers — build a fake OTel module graph that ``_get_otel_modules`` finds
# ---------------------------------------------------------------------------


def _build_otel_mocks() -> dict[str, MagicMock]:
    """Return a dict of mock OTel symbols keyed the same as ``_get_otel_modules``."""
    mock_provider = MagicMock(name="LoggerProvider")
    mock_logger = MagicMock(name="otel_logger")
    mock_provider_instance = MagicMock(name="LoggerProvider()")
    mock_provider_instance.get_logger.return_value = mock_logger
    mock_provider.return_value = mock_provider_instance

    mock_resource = MagicMock(name="Resource")
    mock_resource.create.return_value = MagicMock(name="resource_instance")

    mock_batch = MagicMock(name="BatchLogRecordProcessor")
    mock_simple = MagicMock(name="SimpleLogRecordProcessor")
    mock_log_record = MagicMock(name="LogRecord")

    mock_trace = MagicMock(name="trace")
    span_ctx = MagicMock(name="span_context")
    span_ctx.is_valid = True
    span_ctx.trace_id = 123456
    span_ctx.span_id = 789
    span_ctx.trace_flags = MagicMock()
    mock_trace.get_current_span.return_value.get_span_context.return_value = span_ctx

    return {
        "LoggerProvider": mock_provider,
        "LogRecord": mock_log_record,
        "BatchLogRecordProcessor": mock_batch,
        "SimpleLogRecordProcessor": mock_simple,
        "Resource": mock_resource,
        "trace": mock_trace,
        # extra helpers for assertions
        "_provider_instance": mock_provider_instance,
        "_logger": mock_logger,
        "_span_ctx": span_ctx,
    }


def _mock_grpc_exporter() -> MagicMock:
    return MagicMock(name="GrpcOTLPLogExporter")


def _mock_http_exporter() -> MagicMock:
    return MagicMock(name="HttpOTLPLogExporter")


@pytest.fixture
def otel_mocks() -> dict[str, MagicMock]:
    return _build_otel_mocks()


def _patch_otel(otel_mocks: dict[str, MagicMock], protocol: str = "grpc"):
    """Context-manager that patches both ``_get_otel_modules`` and the exporter."""
    exporter = _mock_grpc_exporter() if protocol == "grpc" else _mock_http_exporter()
    exporter_path = (
        "pykit_logging.otlp._get_grpc_exporter"
        if protocol == "grpc"
        else "pykit_logging.otlp._get_http_exporter"
    )
    return (
        patch("pykit_logging.otlp._get_otel_modules", return_value=otel_mocks),
        patch(exporter_path, return_value=exporter),
        exporter,
    )


# =====================================================================
# OTLPConfig
# =====================================================================


class TestOTLPConfig:
    """Tests for ``OTLPConfig`` frozen dataclass."""

    def test_defaults(self) -> None:
        cfg = OTLPConfig()
        assert cfg.enabled is False
        assert cfg.endpoint == "http://localhost:4317"
        assert cfg.protocol == "grpc"
        assert cfg.insecure is True
        assert cfg.headers == {}

    def test_custom_values(self) -> None:
        cfg = OTLPConfig(
            enabled=True,
            endpoint="https://collector.example.com:443",
            protocol="http",
            insecure=False,
            headers={"Authorization": "Bearer tok"},
        )
        assert cfg.enabled is True
        assert cfg.protocol == "http"
        assert cfg.headers["Authorization"] == "Bearer tok"

    def test_frozen(self) -> None:
        cfg = OTLPConfig()
        with pytest.raises(AttributeError):
            cfg.enabled = True  # type: ignore[misc]


# =====================================================================
# Severity mapping
# =====================================================================


class TestSeverityMap:
    """Verify structlog level → OTel severity mapping."""

    @pytest.mark.parametrize(
        ("level", "expected_number", "expected_text"),
        [
            ("debug", 5, "DEBUG"),
            ("info", 9, "INFO"),
            ("warning", 13, "WARN"),
            ("warn", 13, "WARN"),
            ("error", 17, "ERROR"),
            ("critical", 21, "FATAL"),
            ("fatal", 21, "FATAL"),
        ],
    )
    def test_known_levels(self, level: str, expected_number: int, expected_text: str) -> None:
        num, text = _SEVERITY_MAP[level]
        assert num == expected_number
        assert text == expected_text

    def test_unknown_level_falls_back(self) -> None:
        # The bridge code uses .get(..., (9, "INFO"))
        assert _SEVERITY_MAP.get("unknown_level", (9, "INFO")) == (9, "INFO")


# =====================================================================
# OTLPLogBridge
# =====================================================================


class TestOTLPLogBridge:
    """Tests for ``OTLPLogBridge`` creation and methods."""

    def test_creation_grpc(self, otel_mocks: dict[str, MagicMock]) -> None:
        p1, p2, _exporter_cls = _patch_otel(otel_mocks, "grpc")
        with p1, p2:
            bridge = OTLPLogBridge(
                config=OTLPConfig(enabled=True),
                service_name="test-svc",
                environment="test",
                version="1.0.0",
            )
        otel_mocks["Resource"].create.assert_called_once_with(
            {
                "service.name": "test-svc",
                "deployment.environment": "test",
                "service.version": "1.0.0",
            }
        )
        assert bridge._otel_logger is otel_mocks["_logger"]

    def test_creation_http(self, otel_mocks: dict[str, MagicMock]) -> None:
        p1, p2, _ = _patch_otel(otel_mocks, "http")
        with p1, p2:
            bridge = OTLPLogBridge(
                config=OTLPConfig(enabled=True, protocol="http"),
                service_name="test-svc",
            )
        assert bridge is not None

    def test_emit_creates_log_record(self, otel_mocks: dict[str, MagicMock]) -> None:
        p1, p2, _ = _patch_otel(otel_mocks, "grpc")
        with p1, p2:
            bridge = OTLPLogBridge(config=OTLPConfig(enabled=True), service_name="svc")

        bridge.emit("info", "hello world", {"key": "value"})

        otel_mocks["LogRecord"].assert_called_once()
        call_kwargs = otel_mocks["LogRecord"].call_args
        assert call_kwargs.kwargs["body"] == "hello world"
        assert call_kwargs.kwargs["severity_number"] == 9
        assert call_kwargs.kwargs["severity_text"] == "INFO"
        assert call_kwargs.kwargs["attributes"] == {"key": "value"}
        otel_mocks["_logger"].emit.assert_called_once()

    def test_emit_extracts_trace_context(self, otel_mocks: dict[str, MagicMock]) -> None:
        p1, p2, _ = _patch_otel(otel_mocks, "grpc")
        with p1, p2:
            bridge = OTLPLogBridge(config=OTLPConfig(enabled=True), service_name="svc")

        bridge.emit("error", "oops", {})

        call_kwargs = otel_mocks["LogRecord"].call_args.kwargs
        assert call_kwargs["trace_id"] == 123456
        assert call_kwargs["span_id"] == 789

    def test_emit_handles_no_trace_context(self, otel_mocks: dict[str, MagicMock]) -> None:
        otel_mocks["trace"].get_current_span.side_effect = Exception("no span")
        p1, p2, _ = _patch_otel(otel_mocks, "grpc")
        with p1, p2:
            bridge = OTLPLogBridge(config=OTLPConfig(enabled=True), service_name="svc")

        # Should not raise
        bridge.emit("info", "msg", {})

        call_kwargs = otel_mocks["LogRecord"].call_args.kwargs
        assert call_kwargs["trace_id"] == 0
        assert call_kwargs["span_id"] == 0

    def test_shutdown_calls_provider_shutdown(self, otel_mocks: dict[str, MagicMock]) -> None:
        p1, p2, _ = _patch_otel(otel_mocks, "grpc")
        with p1, p2:
            bridge = OTLPLogBridge(config=OTLPConfig(enabled=True), service_name="svc")

        bridge.shutdown()
        otel_mocks["_provider_instance"].shutdown.assert_called_once()

    def test_shutdown_suppresses_errors(self, otel_mocks: dict[str, MagicMock]) -> None:
        p1, p2, _ = _patch_otel(otel_mocks, "grpc")
        with p1, p2:
            bridge = OTLPLogBridge(config=OTLPConfig(enabled=True), service_name="svc")

        otel_mocks["_provider_instance"].shutdown.side_effect = RuntimeError("boom")
        bridge.shutdown()  # should not raise


# =====================================================================
# _sanitize_attributes
# =====================================================================


class TestSanitizeAttributes:
    """Test attribute sanitisation for OTel compatibility."""

    def test_primitives_pass_through(self) -> None:
        attrs = {"s": "str", "i": 42, "f": 3.14, "b": True}
        assert _sanitize_attributes(attrs) == attrs

    def test_non_primitives_stringified(self) -> None:
        result = _sanitize_attributes({"list": [1, 2], "dict": {"a": 1}})
        assert result["list"] == "[1, 2]"
        assert result["dict"] == "{'a': 1}"


# =====================================================================
# otlp_processor (structlog processor)
# =====================================================================


class TestOTLPProcessor:
    """Tests for the structlog processor factory."""

    def test_returns_event_dict_unchanged(self) -> None:
        mock_bridge = MagicMock(spec=OTLPLogBridge)
        proc = otlp_processor(mock_bridge)
        event = {"event": "test message", "level": "info", "key": "val"}
        result = proc(None, "info", event)
        assert result is event

    def test_calls_bridge_emit(self) -> None:
        mock_bridge = MagicMock(spec=OTLPLogBridge)
        proc = otlp_processor(mock_bridge)
        proc(None, "info", {"event": "hello", "level": "info", "extra": 42})
        mock_bridge.emit.assert_called_once_with("info", "hello", {"extra": 42})

    def test_uses_method_name_when_no_level(self) -> None:
        mock_bridge = MagicMock(spec=OTLPLogBridge)
        proc = otlp_processor(mock_bridge)
        proc(None, "warning", {"event": "msg"})
        mock_bridge.emit.assert_called_once()
        assert mock_bridge.emit.call_args[0][0] == "warning"

    def test_emit_error_does_not_propagate(self) -> None:
        mock_bridge = MagicMock(spec=OTLPLogBridge)
        mock_bridge.emit.side_effect = RuntimeError("network down")
        proc = otlp_processor(mock_bridge)
        result = proc(None, "info", {"event": "msg", "level": "info"})
        assert result["event"] == "msg"

    def test_excludes_record_key(self) -> None:
        mock_bridge = MagicMock(spec=OTLPLogBridge)
        proc = otlp_processor(mock_bridge)
        proc(None, "info", {"event": "msg", "level": "info", "_record": "stdlib"})
        call_args = mock_bridge.emit.call_args[0]
        assert "_record" not in call_args[2]


# =====================================================================
# Missing OTel dependencies
# =====================================================================


class TestMissingDependencies:
    """Ensure helpful error when OTel packages are absent."""

    def test_get_otel_modules_raises_import_error(self) -> None:
        from pykit_logging.otlp import _get_otel_modules

        with patch.dict(sys.modules, {"opentelemetry.sdk._logs": None}), pytest.raises(
            ImportError, match="OpenTelemetry SDK is required"
        ):
            _get_otel_modules()

    def test_get_grpc_exporter_raises_import_error(self) -> None:
        from pykit_logging.otlp import _get_grpc_exporter

        with patch.dict(
            sys.modules, {"opentelemetry.exporter.otlp.proto.grpc._log_exporter": None}
        ), pytest.raises(ImportError, match="gRPC OTLP exporter is required"):
            _get_grpc_exporter()

    def test_get_http_exporter_raises_import_error(self) -> None:
        from pykit_logging.otlp import _get_http_exporter

        with patch.dict(
            sys.modules, {"opentelemetry.exporter.otlp.proto.http._log_exporter": None}
        ), pytest.raises(ImportError, match="HTTP OTLP exporter is required"):
            _get_http_exporter()


# =====================================================================
# shutdown_logging integration
# =====================================================================


class TestShutdownLogging:
    """Test the module-level ``shutdown_logging`` function."""

    def test_shutdown_with_no_bridge(self) -> None:
        from pykit_logging import setup as setup_mod

        setup_mod._otlp_bridge = None
        setup_mod.shutdown_logging()  # should not raise

    def test_shutdown_calls_bridge_shutdown(self) -> None:
        from pykit_logging import setup as setup_mod

        mock_bridge = MagicMock(spec=OTLPLogBridge)
        setup_mod._otlp_bridge = mock_bridge
        setup_mod.shutdown_logging()
        mock_bridge.shutdown.assert_called_once()
        assert setup_mod._otlp_bridge is None

    def test_shutdown_clears_bridge(self) -> None:
        from pykit_logging import setup as setup_mod

        mock_bridge = MagicMock(spec=OTLPLogBridge)
        setup_mod._otlp_bridge = mock_bridge
        setup_mod.shutdown_logging()
        assert setup_mod._otlp_bridge is None


# =====================================================================
# setup_logging integration with OTLP
# =====================================================================


class TestSetupLoggingOTLPIntegration:
    """Test that ``setup_logging`` correctly wires the OTLP bridge."""

    def test_setup_without_otlp_works(self) -> None:
        from pykit_logging.setup import setup_logging

        setup_logging(level="DEBUG", service_name="test")  # should not raise

    def test_setup_with_disabled_otlp_skips_bridge(self) -> None:
        from pykit_logging import setup as setup_mod
        from pykit_logging.setup import setup_logging

        setup_mod._otlp_bridge = None
        setup_logging(level="DEBUG", service_name="test", otlp=OTLPConfig(enabled=False))
        assert setup_mod._otlp_bridge is None

    def test_setup_with_enabled_otlp_creates_bridge(self, otel_mocks: dict[str, MagicMock]) -> None:
        from pykit_logging import setup as setup_mod
        from pykit_logging.setup import setup_logging

        p1, p2, _ = _patch_otel(otel_mocks, "grpc")
        with p1, p2:
            setup_logging(
                level="DEBUG",
                service_name="test-svc",
                otlp=OTLPConfig(enabled=True),
            )
        assert setup_mod._otlp_bridge is not None
        # Cleanup
        setup_mod._otlp_bridge = None
