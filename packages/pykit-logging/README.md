# pykit-logging

Structured logging with JSON production output, human-readable development output, and correlation ID tracking.

## Installation

```bash
pip install pykit-logging
# or
uv add pykit-logging
```

## Quick Start

```python
from pykit_logging import setup_logging, get_logger

# Configure once at startup
setup_logging(level="INFO", log_format="auto", service_name="my-service")
# "auto" → JSON in production, console in development

logger = get_logger("my_module")
logger.info("request processed", user_id="abc", duration_ms=42)

# Correlation ID tracking for distributed tracing
from pykit_logging.setup import set_correlation_id, new_correlation_id

cid = set_correlation_id()  # auto-generates UUID
# All subsequent log entries include correlation_id
logger.info("handling request")  # → {"correlation_id": "...", ...}
```

## Key Components

- **setup_logging(level, log_format, service_name)** — Configure structured logging; `log_format` accepts `"json"` (production), `"console"` (development), or `"auto"` (auto-detect); adds ISO timestamps, stack info, and service name to all entries
- **get_logger(name)** — Returns a `structlog.stdlib.BoundLogger` instance for structured key-value logging
- **set_correlation_id(cid)** — Set or auto-generate a correlation ID for the current async/thread context; added to all log entries via a structlog processor
- **new_correlation_id()** — Generate a new UUID-based correlation ID
- **correlation_id_var** — `ContextVar[str]` for manual correlation ID management

## Dependencies

- `structlog` — Structured logging library

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
