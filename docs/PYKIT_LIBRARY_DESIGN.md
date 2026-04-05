# pykit — Python Infrastructure Library Design

> Standalone Python infrastructure library mirroring **gokit** (Go) and **rskit** (Rust).
> Bootstrap: copy existing `sentinel/py-services/pykit/` → `pykit/`, then expand to full parity.

---

## 1. Vision

pykit is the Python member of a cross-language kit ecosystem:

| Kit | Language | Structure |
|-----|----------|-----------|
| **gokit** | Go | Root module + 18 sub-modules — **the reference implementation** |
| **rskit** | Rust | 31 crates in workspace — mirrors gokit |
| **pykit** | Python | uv workspace, core + sub-packages — mirrors gokit |

**Principles**: same module names, same patterns, same output for same input. Python idioms (Protocol, async/await, Pydantic, structlog) replace Go/Rust idioms.

---

## 2. Cross-Language Module Map

Legend: ✅ exists in sentinel pykit (copy as-is) · ⬜ needs building

### Foundation

| Module | gokit | rskit | pykit | Status |
|--------|-------|-------|-------|--------|
| errors | `errors/` | `rskit-errors` | `pykit-errors` | ✅ copy from sentinel |
| config | `config/` | `rskit-config` | `pykit-config` | ✅ copy from sentinel |
| logging | `logger/` | `rskit-logging` | `pykit-logging` | ✅ copy from sentinel |
| validation | `validation/` | `rskit-validation` | `pykit-validation` | ⬜ build |
| encryption | `encryption/` | — | `pykit-encryption` | ⬜ build |
| util | `util/` | — | `pykit-util` | ⬜ build |
| version | `version/` | — | `pykit-version` | ⬜ build |
| media | `media/` | `rskit-media` | `pykit-media` | ⬜ build |

### Core Architecture

| Module | gokit | rskit | pykit | Status |
|--------|-------|-------|-------|--------|
| provider | `provider/` | `rskit-provider` | `pykit-provider` | ✅ copy from sentinel |
| component | `component/` | (in bootstrap) | `pykit-component` | ⬜ build |
| di | `di/` | `rskit-di` | `pykit-di` | ⬜ build |
| bootstrap | `bootstrap/` | `rskit-bootstrap` | `pykit-bootstrap` | ⬜ build |
| resilience | `resilience/` | `rskit-resilience` | `pykit-resilience` | ⬜ build |
| observability | `observability/` | `rskit-observability` | `pykit-observability` | ⬜ build |
| security | `security/` | — | `pykit-security` | ⬜ build |

### Data & Flow

| Module | gokit | rskit | pykit | Status |
|--------|-------|-------|-------|--------|
| pipeline | `pipeline/` | `rskit-pipeline` | `pykit-pipeline` | ✅ copy from sentinel |
| dag | `dag/` | `rskit-dag` | `pykit-dag` | ⬜ build |
| worker | `worker/` | `rskit-worker` | `pykit-worker` | ⬜ build |
| sse | `sse/` | `rskit-sse` | `pykit-sse` | ⬜ build |
| stateful | `stateful/` | — | `pykit-stateful` | ⬜ build |

### Infrastructure

| Module | gokit | rskit | pykit | Status |
|--------|-------|-------|-------|--------|
| database | `database/` | `rskit-database` | `pykit-database` | ⬜ build |
| redis | `redis/` | `rskit-cache` | `pykit-redis` | ⬜ build |
| storage | `storage/` | `rskit-file` | `pykit-storage` | ⬜ build |
| messaging | `messaging/` | `rskit-messaging` | `pykit-messaging` | ✅ complete |
| httpclient | `httpclient/` | `rskit-http` | `pykit-httpclient` | ⬜ build |

### Servers

| Module | gokit | rskit | pykit | Status |
|--------|-------|-------|-------|--------|
| server (HTTP) | `server/` | `rskit-http` | `pykit-server` | ✅ copy from sentinel (gRPC) |
| grpc | `grpc/` | `rskit-server` | `pykit-grpc` | ⬜ build (client-side) |
| connect | `connect/` | — | — | skip for now |

### Security

| Module | gokit | rskit | pykit | Status |
|--------|-------|-------|-------|--------|
| auth | `auth/` | `rskit-auth` | `pykit-auth` | ⬜ build |
| authz | `authz/` | `rskit-authz` | `pykit-authz` | ⬜ build |

### AI/ML

| Module | gokit | rskit | pykit | Status |
|--------|-------|-------|-------|--------|
| llm | `llm/` | `rskit-llm` | `pykit-llm` | ⬜ build |
| triton | — | — | `pykit-triton` | ✅ copy from sentinel |
| bench | `bench/` | `rskit-bench` | `pykit-bench` | ✅ copy from sentinel |
| dataset | — | `rskit-dataset` | `pykit-dataset` | ✅ copy from sentinel |

### Platform

| Module | gokit | rskit | pykit | Status |
|--------|-------|-------|-------|--------|
| discovery | `discovery/` | `rskit-discovery` | `pykit-discovery` | ⬜ build |
| process | `process/` | — | `pykit-process` | ⬜ build |
| workload | `workload/` | — | `pykit-workload` | ⬜ build |

### Testing

| Module | gokit | rskit | pykit | Status |
|--------|-------|-------|-------|--------|
| testutil | `testutil/` | `rskit-testutil` | `pykit-testutil` | ✅ copy from sentinel (as `testing`) |
| metrics | — | — | `pykit-metrics` | ✅ copy from sentinel |

### Summary: 11 modules copy from sentinel, ~22 modules to build

---

## 3. Repository Structure

```
pykit/                              # git root
├── pyproject.toml                  # workspace root
├── uv.lock
├── README.md
├── CHANGELOG.md
├── docs/
│
├── packages/
│   ├── pykit/                      # facade — re-exports everything
│   │   ├── pyproject.toml
│   │   └── src/pykit/__init__.py
│   │
│   │── # ── Foundation ──────────────────
│   ├── pykit-errors/
│   │   ├── pyproject.toml
│   │   └── src/pykit_errors/
│   │       ├── __init__.py
│   │       ├── codes.py            # ErrorCode enum
│   │       └── base.py             # AppError, typed exceptions
│   │
│   ├── pykit-config/
│   │   ├── pyproject.toml
│   │   └── src/pykit_config/
│   │       ├── __init__.py
│   │       └── settings.py         # BaseSettings (Pydantic)
│   │
│   ├── pykit-logging/
│   │   ├── pyproject.toml
│   │   └── src/pykit_logging/
│   │       ├── __init__.py
│   │       └── setup.py            # structlog setup, correlation ID
│   │
│   ├── pykit-validation/
│   ├── pykit-encryption/
│   ├── pykit-util/
│   ├── pykit-version/
│   ├── pykit-media/
│   │
│   │── # ── Core Architecture ───────────
│   ├── pykit-provider/
│   │   ├── pyproject.toml
│   │   └── src/pykit_provider/
│   │       ├── __init__.py
│   │       ├── base.py             # 4 provider protocols
│   │       ├── func.py             # ProviderFunc wrappers
│   │       ├── registry.py         # Registry, Manager, Selector
│   │       └── middleware.py       # Chain, WithLogging, WithMetrics
│   │
│   ├── pykit-component/
│   ├── pykit-di/
│   ├── pykit-bootstrap/
│   ├── pykit-resilience/
│   ├── pykit-observability/
│   │
│   │── # ── Data & Flow ─────────────────
│   ├── pykit-pipeline/
│   ├── pykit-dag/
│   ├── pykit-worker/
│   ├── pykit-sse/
│   ├── pykit-stateful/
│   │
│   │── # ── Infrastructure ──────────────
│   ├── pykit-database/
│   ├── pykit-redis/
│   ├── pykit-storage/
│   ├── pykit-messaging/
│   ├── pykit-httpclient/
│   │
│   │── # ── Servers ─────────────────────
│   ├── pykit-server/
│   ├── pykit-grpc/
│   │
│   │── # ── Security ────────────────────
│   ├── pykit-auth/
│   ├── pykit-authz/
│   │
│   │── # ── AI/ML ───────────────────────
│   ├── pykit-llm/
│   ├── pykit-triton/
│   ├── pykit-bench/
│   ├── pykit-dataset/
│   │
│   │── # ── Platform ────────────────────
│   ├── pykit-discovery/
│   ├── pykit-process/
│   ├── pykit-workload/
│   │
│   │── # ── Testing ─────────────────────
│   ├── pykit-testutil/
│   └── pykit-metrics/
│
└── examples/
```

---

## 4. Copying Sentinel pykit Modules

The existing sentinel pykit lives at `sentinel/py-services/pykit/src/pykit/`. Each sub-module maps to a standalone package:

| Sentinel module | → pykit package | Notes |
|-----------------|-----------------|-------|
| `errors/` | `packages/pykit-errors/` | Direct copy, rename imports |
| `config/` | `packages/pykit-config/` | Direct copy |
| `logging/` | `packages/pykit-logging/` | Direct copy |
| `provider/` | `packages/pykit-provider/` | Direct copy |
| `pipeline/` | `packages/pykit-pipeline/` | Direct copy |
| `server/` | `packages/pykit-server/` | Direct copy (gRPC server) |
| `metrics/` | `packages/pykit-metrics/` | Direct copy (Prometheus) |
| `testing/` | `packages/pykit-testutil/` | Rename to testutil |
| `triton/` | `packages/pykit-triton/` | Direct copy |
| `dataset/` | `packages/pykit-dataset/` | Direct copy (incl. sources/, targets/) |
| `bench/` | `packages/pykit-bench/` | Direct copy (incl. metric/, viz/, report_gen/) |

**Migration steps per module:**

1. Create `packages/pykit-{name}/pyproject.toml` with deps (no versions)
2. Copy source files to `packages/pykit-{name}/src/pykit_{name}/`
3. Update imports: `from pykit.errors` → `from pykit_errors`
4. Copy tests to `packages/pykit-{name}/tests/`
5. Verify: `uv run pytest packages/pykit-{name}/`

---

## 5. pyproject.toml Structure

### Root workspace

```toml
[project]
name = "pykit-workspace"
version = "0.1.0"
requires-python = ">=3.13"

[tool.uv.workspace]
members = ["packages/*"]

[tool.uv]
constraint-dependencies = [
    "pydantic>=2.12.0,<3.0",
    "pydantic-settings>=2.7",
    "structlog>=25.1.0",
    "grpcio>=1.70",
    "grpcio-health-checking>=1.70",
    "grpcio-reflection>=1.70",
    "prometheus-client>=0.22",
    "httpx>=0.28",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30",
    "redis>=5.2",
    "aiokafka>=0.12",
    "opentelemetry-api>=1.30",
    "opentelemetry-sdk>=1.30",
    "pyjwt>=2.10",
    "cryptography>=44.0",
    "tritonclient[grpc]>=2.50",
]

[tool.uv.sources]
pykit-errors   = { workspace = true }
pykit-config   = { workspace = true }
pykit-logging  = { workspace = true }
pykit-provider = { workspace = true }
pykit-pipeline = { workspace = true }
# ... all packages
```

### Sub-package example (pykit-errors)

```toml
[project]
name = "pykit-errors"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = []  # zero deps — foundation layer

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/pykit_errors"]
```

### Sub-package example (pykit-provider)

```toml
[project]
name = "pykit-provider"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "pykit-errors",   # no version — central constraints
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/pykit_provider"]
```

---

## 6. Layer Architecture

Strict import rules — a layer may only import from layers below it:

```
Layer 0  errors, config, logging              (zero internal deps)
Layer 1  validation, encryption, util, version, media
Layer 2  provider, component, resilience       (→ Layer 0)
Layer 3  di, bootstrap, observability          (→ Layer 0-2)
Layer 4  pipeline, dag, worker, sse, stateful  (→ Layer 0-2)
Layer 5  auth, authz, security                 (→ Layer 0-2)
Layer 6  database, redis, storage, messaging, httpclient  (→ Layer 0-3)
Layer 7  server, grpc                          (→ Layer 0-6)
Layer 8  llm, triton, bench, dataset           (→ Layer 0-4)
Layer 9  discovery, workload, process, testutil, metrics
```

Enforce with `import-linter` in CI.

---

## 7. Implementation Phases

### Phase 1 — Extract & Scaffold

- Create `pykit/` repo with uv workspace
- Copy 11 sentinel modules (see §4)
- Fix imports, add per-package pyproject.toml
- All tests green

### Phase 2 — Missing Foundation

Build modules that gokit/rskit have but sentinel pykit doesn't:

- **validation** — Pydantic-based field validation, mirrors gokit `validation/`
- **encryption** — AES-256-GCM via `cryptography`, mirrors gokit `encryption/`
- **util** — Generic helpers (retry decorator, slug, deep merge)
- **version** — Build metadata injection
- **component** — `Component` protocol (name, start, stop, health), `Registry`
- **di** — Lightweight DI container
- **bootstrap** — `App` lifecycle (configure → start → ready → shutdown), hooks
- **resilience** — Circuit breaker, retry, bulkhead, rate limiter (tenacity + custom)

### Phase 3 — Infrastructure Adapters

- **database** — Async SQLAlchemy wrapper, repository pattern, migrations
- **redis** — Redis async client wrapper, typed store, component lifecycle
- **storage** — Local/S3 file storage abstraction
- **messaging** — Message producer/consumer abstraction with aiokafka provider and in-memory broker for testing
- **httpclient** — httpx wrapper with resilience middleware

### Phase 4 — Servers & Security

- **grpc** — gRPC client utilities (already have server from sentinel)
- **auth** — JWT validation, OIDC, password hashing (bcrypt/argon2)
- **authz** — RBAC permission checking, wildcard patterns
- **observability** — OpenTelemetry tracing + metrics

### Phase 5 — Advanced

- **dag** — DAG execution engine (batch + streaming modes)
- **worker** — Async task pool with events (progress, partial, complete)
- **sse** — Server-Sent Events hub
- **stateful** — Stateful provider wrapper with context store
- **llm** — LLM provider abstractions (Ollama, OpenAI, Anthropic)
- **discovery** — Service discovery with load balancing
- **process** — Subprocess execution with signal handling

---

## 8. Key Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Config | Pydantic Settings | Env var loading, validation, type safety built-in |
| Logging | structlog | Structured JSON, context binding, processors |
| Async | async-first | Python ML/AI ecosystem is async; matches gokit's goroutines |
| Database | SQLAlchemy async | ORM + raw SQL, migration support, broad DB support |
| Types | Protocol (structural) | Duck-typing; no inheritance required; runtime_checkable |
| Data | frozen dataclass + slots | Immutable, memory-efficient, hashable |
| Package manager | uv workspace | Fast, lockfile, workspace support, constraint-dependencies |
| HTTP client | httpx | Async-native, similar API to requests |
| Resilience | tenacity + custom | Mature retry library; circuit breaker custom like gokit |
