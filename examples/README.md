# pykit Examples

Practical, self-contained scripts demonstrating pykit packages.

| File | What it shows |
|------|--------------|
| [`errors_and_config.py`](errors_and_config.py) | AppError hierarchy, BaseSettings env-var config, structured logging |
| [`validation_and_encryption.py`](validation_and_encryption.py) | Fluent Validator chains, AES-GCM / Fernet encrypt-decrypt |
| [`resilience_patterns.py`](resilience_patterns.py) | Circuit breaker, retry with backoff, token-bucket rate limiter |
| [`di_and_bootstrap.py`](di_and_bootstrap.py) | DI Container, App lifecycle hooks, Component Registry |
| [`database_and_cache.py`](database_and_cache.py) | Async SQLite Repository (aiosqlite), cache TypedStore |
| [`dag_and_worker.py`](dag_and_worker.py) | DAG construction & execution, concurrent WorkerPool |
| [`media_detection.py`](media_detection.py) | Detect JPEG, PNG, MP3, MP4, text from raw bytes |

## Running

Each file is a standalone script:

```bash
cd pykit
uv run python examples/errors_and_config.py
```

> **Note:** `database_and_cache.py` requires a running cache server for the
> cache portion. The SQLite section works out of the box.
