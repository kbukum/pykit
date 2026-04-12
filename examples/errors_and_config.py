"""Example: Foundation layer — errors, config, logging.

Demonstrates:
- Creating and catching AppError and its subclasses
- Using BaseSettings to load configuration from environment variables
- Setting up structured logging with pykit_logging
"""

from __future__ import annotations

import os


def demo_errors() -> None:
    """Show how to raise and catch domain-specific errors."""
    from pykit_errors import AppError, InvalidInputError, NotFoundError

    # Basic AppError with optional details dict
    err = AppError("something went wrong", details={"request_id": "abc-123"})
    print(f"AppError : {err} | details={err.details}")

    # Specialized errors carry semantic meaning
    not_found = NotFoundError("User", "42")
    print(f"NotFoundError : {not_found}")

    invalid = InvalidInputError("email is required", field="email")
    print(f"InvalidInputError: {invalid}")

    # Catch any pykit error via the base class
    try:
        raise NotFoundError("Order", "99")
    except AppError as exc:
        print(f"Caught AppError subclass: {type(exc).__name__}: {exc}")


def demo_config() -> None:
    """Show how BaseSettings reads env vars automatically."""
    from pykit_config import BaseSettings

    # Simulate environment variables (in production these come from .env / k8s)
    os.environ["SERVICE_NAME"] = "order-service"
    os.environ["ENVIRONMENT"] = "staging"
    os.environ["SERVICE_PORT"] = "8080"
    os.environ["LOG_LEVEL"] = "DEBUG"

    settings = BaseSettings()
    print(f"\nConfig → service={settings.service_name}, env={settings.environment}")
    print(f"         port={settings.service_port}, log_level={settings.log_level}")
    print(f"         is_production={settings.is_production}")


def demo_logging() -> None:
    """Show structured logging with correlation IDs."""
    from pykit_logging import get_logger, setup_logging

    setup_logging(level="DEBUG", log_format="console", service_name="order-service")
    log = get_logger("example")

    log.info("server.starting", port=8080)
    log.debug("loading config", source="env")
    log.warning("cache miss", key="user:42")

    # Structured context travels with the logger
    bound = log.bind(request_id="req-abc")
    bound.info("handling request", path="/orders")
    bound.info("request complete", status=200, duration_ms=42)


if __name__ == "__main__":
    demo_errors()
    demo_config()
    demo_logging()
