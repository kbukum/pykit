"""Structured logging — JSON in production, human-readable in development."""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

import structlog

from pykit_logging.masking import DefaultMasker, MaskingConfig, masking_processor
from pykit_logging.module_levels import ModuleLevelsConfig, module_levels_processor
from pykit_logging.otlp import OTLPConfig, OTLPLogBridge, otlp_processor
from pykit_logging.sampling import SamplingConfig, sampling_processor

# Correlation ID for request tracing
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def new_correlation_id() -> str:
    """Generate a new correlation ID."""
    return str(uuid.uuid4())


def set_correlation_id(cid: str | None = None) -> str:
    """Set (or generate) a correlation ID for the current context."""
    cid = cid or new_correlation_id()
    correlation_id_var.set(cid)
    return cid


def add_correlation_id(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Structlog processor that adds the current correlation ID."""
    cid = correlation_id_var.get("")
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict


def schema_normalizer(service_name: str, environment: str = "development") -> structlog.types.Processor:
    """Create a processor that adds standard service fields to every log entry.

    Args:
        service_name: The name of the service emitting logs.
        environment: Deployment environment (e.g. ``"production"``, ``"development"``).

    Returns:
        A structlog processor function.
    """

    def _processor(
        logger: Any,
        method_name: str,
        event_dict: dict[str, Any],
    ) -> dict[str, Any]:
        event_dict["service"] = service_name
        event_dict["environment"] = environment
        return event_dict

    return _processor  # type: ignore[return-value]


# Module-level OTLP bridge for graceful shutdown
_otlp_bridge: OTLPLogBridge | None = None


def setup_logging(
    *,
    level: str = "INFO",
    log_format: str = "auto",
    service_name: str = "pykit",
    masking: MaskingConfig | None = None,
    sampling: SamplingConfig | None = None,
    module_levels: dict[str, str] | None = None,
    environment: str = "development",
    otlp: OTLPConfig | None = None,
) -> None:
    """Configure structured logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR).
        log_format: "json" for production, "console" for development,
            "auto" to detect (uses JSON when stderr is not a TTY, console otherwise).
        service_name: Added to every log entry.
        masking: Masking configuration. Defaults to ``MaskingConfig(enabled=True)``.
        sampling: Sampling configuration. ``None`` disables sampling.
        module_levels: Per-module log level overrides, e.g. ``{"aiokafka": "CRITICAL"}``.
        environment: Deployment environment label added to every log entry.
        otlp: OTLP export configuration. ``None`` disables OTLP export.
    """
    global _otlp_bridge
    if log_format == "auto":
        log_format = "console" if sys.stderr.isatty() else "json"

    if masking is None:
        masking = MaskingConfig()

    # Configure standard logging to suppress noisy third-party libraries
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(level=log_level, stream=sys.stderr, format="%(message)s")

    # Suppress noisy Kafka client internals
    logging.getLogger("aiokafka").setLevel(logging.CRITICAL)
    logging.getLogger("kafka").setLevel(logging.CRITICAL)

    # Suppress noisy HTTP client request logging (e.g. Consul registration)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        add_correlation_id,  # type: ignore[list-item]
        structlog.processors.add_log_level,
        schema_normalizer(service_name, environment),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if module_levels:
        shared_processors.append(
            module_levels_processor(ModuleLevelsConfig(levels=module_levels)),
        )

    if sampling and sampling.enabled:
        shared_processors.append(sampling_processor(sampling))

    if masking.enabled:
        shared_processors.append(masking_processor(DefaultMasker(masking)))

    # OTLP bridge — must be after masking so exported logs are already masked
    if otlp and otlp.enabled:
        try:
            bridge = OTLPLogBridge(config=otlp, service_name=service_name, environment=environment)
            shared_processors.append(otlp_processor(bridge))
            _otlp_bridge = bridge
        except ImportError:
            import logging as _stdlib_logging

            _stdlib_logging.getLogger("pykit.logging").warning(
                "OTLP log export requested but dependencies are not installed. "
                "Install with: pip install pykit-logging[otlp] — "
                "falling back to stdout-only logging.",
            )

    if log_format == "json":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper(), logging.INFO)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def shutdown_logging() -> None:
    """Shutdown OTLP bridge gracefully. Call before process exit."""
    global _otlp_bridge
    if _otlp_bridge is not None:
        _otlp_bridge.shutdown()
        _otlp_bridge = None


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]
