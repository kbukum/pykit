# pykit

Convenience facade that re-exports the public API of every pykit sub-package with lazy loading.

## Installation

```bash
pip install pykit
# or
uv add pykit
```

## Quick Start

```python
# Lazy-loaded access — sub-packages are imported on first use
import pykit

# Access any sub-package as an attribute
from pykit.errors import AppError, ErrorCode
from pykit.config import load_config
from pykit.logging import setup_logging, get_logger

# Or use the attribute-style access
enc = pykit.encryption.new_encryptor("my-secret-key")
ciphertext = enc.encrypt("hello world")

# Direct sub-package imports also work
import pykit_errors
err = pykit_errors.AppError.not_found("User", "abc")
```

## Key Components

- **Lazy `__getattr__`** — Sub-packages are only imported on first access, keeping `import pykit` fast even with heavy transitive dependencies (OpenTelemetry, httpx, SQLAlchemy, etc.)
- **`_SUBPACKAGES` mapping** — Maps short names (e.g., `errors`) to actual package names (e.g., `pykit_errors`); `pykit.kafka` maps to `pykit_messaging`
- **Layered architecture** — 34 sub-packages organized in 10 layers from foundational (errors, config, logging) through infrastructure (database, redis) to AI/ML (llm, triton, dataset)

## Dependencies

Installs all 34 pykit sub-packages:

| Layer | Packages |
|-------|----------|
| 0 — Core | pykit-errors, pykit-config, pykit-logging |
| 1 — Foundational | pykit-validation, pykit-encryption, pykit-util, pykit-version, pykit-media |
| 2 — Patterns | pykit-provider, pykit-component, pykit-resilience |
| 3 — Frameworks | pykit-di, pykit-bootstrap, pykit-observability, pykit-security |
| 4 — Infrastructure | pykit-database, pykit-redis, pykit-storage, pykit-messaging, pykit-httpclient |
| 5 — Protocols | pykit-server, pykit-grpc |
| 6 — Security | pykit-auth, pykit-authz |
| 7 — Advanced | pykit-pipeline, pykit-dag, pykit-worker, pykit-sse, pykit-stateful, pykit-process, pykit-workload |
| 8 — AI/ML | pykit-llm, pykit-triton, pykit-dataset |
| 9 — Tools | pykit-metrics, pykit-bench, pykit-testutil, pykit-discovery |

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
