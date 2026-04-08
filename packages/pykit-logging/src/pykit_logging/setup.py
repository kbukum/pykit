"""Structured logging — JSON in production, human-readable in development."""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

import structlog

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


def setup_logging(
    *,
    level: str = "INFO",
    log_format: str = "auto",
    service_name: str = "pykit",
) -> None:
    """Configure structured logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR).
        log_format: "json" for production, "console" for development, "auto" to detect.
        service_name: Added to every log entry.
    """
    if log_format == "auto":
        log_format = "console"

    # Configure standard logging to suppress noisy third-party libraries
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(level=log_level, stream=sys.stderr, format="%(message)s")

    # Suppress noisy Kafka client internals — reconnection is handled by pykit
    logging.getLogger("aiokafka").setLevel(logging.CRITICAL)
    logging.getLogger("kafka").setLevel(logging.CRITICAL)

    # Suppress noisy HTTP client request logging (e.g. Consul registration)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        add_correlation_id,  # type: ignore[list-item]
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

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


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]
