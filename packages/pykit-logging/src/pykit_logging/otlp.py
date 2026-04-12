"""OpenTelemetry Logs bridge with OTLP export.

Bridges structlog output to an OpenTelemetry Collector via the OTel Python SDK.
All OTel dependencies are optional — import them lazily and raise a helpful error
if they are not installed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from opentelemetry.sdk._logs import LoggerProvider

_SEVERITY_MAP: dict[str, tuple[int, str]] = {
    "debug": (5, "DEBUG"),
    "info": (9, "INFO"),
    "warning": (13, "WARN"),
    "warn": (13, "WARN"),
    "error": (17, "ERROR"),
    "critical": (21, "FATAL"),
    "fatal": (21, "FATAL"),
}
"""Map structlog level names to OTel severity (number, text)."""


def _get_otel_modules() -> dict[str, Any]:
    """Lazily import OpenTelemetry modules.

    Returns:
        A dict of required OTel symbols.

    Raises:
        ImportError: If OpenTelemetry SDK packages are not installed.
    """
    try:
        from opentelemetry import trace  # noqa: TC002
        from opentelemetry.sdk._logs import LoggerProvider as _LoggerProvider
        from opentelemetry.sdk._logs import LogRecord
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, SimpleLogRecordProcessor
        from opentelemetry.sdk.resources import Resource
    except ImportError as exc:
        msg = (
            "OpenTelemetry SDK is required for OTLP export. "
            "Install with: pip install opentelemetry-sdk "
            "opentelemetry-exporter-otlp-proto-grpc opentelemetry-exporter-otlp-proto-http"
        )
        raise ImportError(msg) from exc

    return {
        "LoggerProvider": _LoggerProvider,
        "LogRecord": LogRecord,
        "BatchLogRecordProcessor": BatchLogRecordProcessor,
        "SimpleLogRecordProcessor": SimpleLogRecordProcessor,
        "Resource": Resource,
        "trace": trace,
    }


def _get_grpc_exporter() -> Any:
    """Lazily import the gRPC OTLP log exporter.

    Returns:
        The ``OTLPLogExporter`` class for gRPC.

    Raises:
        ImportError: If the gRPC exporter package is not installed.
    """
    try:
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
    except ImportError as exc:
        msg = (
            "gRPC OTLP exporter is required. "
            "Install with: pip install opentelemetry-exporter-otlp-proto-grpc"
        )
        raise ImportError(msg) from exc
    return OTLPLogExporter


def _get_http_exporter() -> Any:
    """Lazily import the HTTP OTLP log exporter.

    Returns:
        The ``OTLPLogExporter`` class for HTTP/protobuf.

    Raises:
        ImportError: If the HTTP exporter package is not installed.
    """
    try:
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    except ImportError as exc:
        msg = (
            "HTTP OTLP exporter is required. "
            "Install with: pip install opentelemetry-exporter-otlp-proto-http"
        )
        raise ImportError(msg) from exc
    return OTLPLogExporter


@dataclass(frozen=True)
class OTLPConfig:
    """Configuration for OTLP log export.

    Attributes:
        enabled: Whether OTLP export is active.
        endpoint: Collector endpoint URL.
        protocol: Transport protocol — ``"grpc"`` or ``"http"``.
        insecure: Disable TLS verification (development only).
        headers: Extra headers sent with every export request.
    """

    enabled: bool = False
    endpoint: str = "http://localhost:4317"
    protocol: str = "grpc"
    insecure: bool = True
    headers: dict[str, str] = field(default_factory=dict)


class OTLPLogBridge:
    """Bridge between structlog and OpenTelemetry LoggerProvider.

    Creates an OTel ``LoggerProvider`` with a ``BatchLogRecordProcessor``
    and the appropriate OTLP exporter (gRPC or HTTP).

    Args:
        config: OTLP export configuration.
        service_name: Logical service name for the ``Resource``.
        environment: Deployment environment label.
        version: Service version string.
    """

    def __init__(
        self,
        config: OTLPConfig,
        service_name: str,
        environment: str = "development",
        version: str = "0.0.0",
    ) -> None:
        self._config = config
        self._service_name = service_name
        self._environment = environment
        self._version = version

        otel = _get_otel_modules()

        resource = otel["Resource"].create(
            {
                "service.name": service_name,
                "deployment.environment": environment,
                "service.version": version,
            }
        )

        exporter = self._create_exporter(config)

        self._provider: LoggerProvider = otel["LoggerProvider"](resource=resource)
        self._provider.add_log_record_processor(otel["BatchLogRecordProcessor"](exporter))
        self._otel_logger = self._provider.get_logger(service_name)
        self._otel = otel

    # -- public API -----------------------------------------------------------

    def emit(self, level: str, message: str, fields: dict[str, Any]) -> None:
        """Emit a log record to the OTLP collector.

        Args:
            level: Log level name (e.g. ``"info"``).
            message: Human-readable log message.
            fields: Additional structured attributes.
        """
        severity_number, severity_text = _SEVERITY_MAP.get(level.lower(), (9, "INFO"))

        trace_id = 0
        span_id = 0
        trace_flags = None

        try:
            span_ctx = self._otel["trace"].get_current_span().get_span_context()
            if span_ctx and span_ctx.is_valid:
                trace_id = span_ctx.trace_id
                span_id = span_ctx.span_id
                trace_flags = span_ctx.trace_flags
        except Exception:  # noqa: BLE001
            pass

        record = self._otel["LogRecord"](
            body=message,
            severity_number=severity_number,
            severity_text=severity_text,
            attributes=_sanitize_attributes(fields),
            trace_id=trace_id,
            span_id=span_id,
            trace_flags=trace_flags,
        )
        self._otel_logger.emit(record)

    def shutdown(self) -> None:
        """Gracefully shutdown, flushing pending logs."""
        try:
            self._provider.shutdown()
        except Exception:  # noqa: BLE001
            logging.getLogger(__name__).debug("Error during OTLP bridge shutdown", exc_info=True)

    # -- internals ------------------------------------------------------------

    @staticmethod
    def _create_exporter(config: OTLPConfig) -> Any:
        """Instantiate the OTLP exporter matching *config.protocol*.

        Args:
            config: OTLP configuration.

        Returns:
            An exporter instance.
        """
        if config.protocol == "http":
            exporter_cls = _get_http_exporter()
        else:
            exporter_cls = _get_grpc_exporter()

        return exporter_cls(
            endpoint=config.endpoint,
            insecure=config.insecure,
            headers=config.headers or None,
        )


def _sanitize_attributes(fields: dict[str, Any]) -> dict[str, str | int | float | bool]:
    """Convert attribute values to OTel-compatible primitive types.

    Args:
        fields: Raw structlog fields.

    Returns:
        A new dict with values coerced to primitives.
    """
    sanitized: dict[str, str | int | float | bool] = {}
    for key, value in fields.items():
        if isinstance(value, (str, int, float, bool)):
            sanitized[key] = value
        else:
            sanitized[key] = str(value)
    return sanitized


def otlp_processor(bridge: OTLPLogBridge) -> structlog.types.Processor:
    """Create a structlog processor that emits log records via OTLP.

    The processor fires-and-forgets to the bridge so that the normal
    stdout/stderr rendering pipeline is not blocked.

    Args:
        bridge: An initialised OTLP log bridge.

    Returns:
        A structlog processor function.
    """

    def _processor(
        logger: Any,
        method_name: str,
        event_dict: dict[str, Any],
    ) -> dict[str, Any]:
        level = event_dict.get("level", method_name)
        message = event_dict.get("event", "")

        extra: dict[str, Any] = {
            k: v for k, v in event_dict.items() if k not in {"event", "level", "_record"}
        }

        try:
            bridge.emit(level, str(message), extra)
        except Exception:  # noqa: BLE001
            logging.getLogger(__name__).debug("OTLP emit failed", exc_info=True)

        return event_dict

    return _processor  # type: ignore[return-value]
