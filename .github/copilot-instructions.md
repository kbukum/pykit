# pykit

Python infrastructure toolkit providing foundational packages for service development. Mirrors gokit (Go) and rskit (Rust) in module structure and naming.

## Build, Test, and Lint

Requires: Python 3.13+, uv.

```bash
uv sync                     # Install all dependencies
uv run pytest               # Run all tests
uv run pytest --cov         # Run tests with coverage (minimum 60%)
uv run ruff check packages/ # Lint
uv run ruff format packages/# Format
uv run mypy                 # Type check (strict mode)
uv run import-linter        # Verify layer architecture compliance
```

## Package Structure

uv workspace monorepo with 35+ packages in `packages/`. Each package has its own `pyproject.toml`.

The root `pykit` package is a lazy-loading facade that re-exports all sub-packages.

**Layers** (enforced by import-linter — lower layers must not import higher):

| Layer | Packages |
|-------|----------|
| Foundation | errors, config, logging |
| Core | validation, encryption, util, version, media |
| Component | component, provider, resilience |
| Infrastructure | di, bootstrap, pipeline, dag, observability |
| Adapters | database, redis, storage, kafka, httpclient |
| Server | server, grpc, sse |
| Security | auth, authz, security |
| Specialist | llm, stateful, worker, process, workload |
| Platform | discovery, testutil, metrics |
| Data | dataset, bench, triton |

## Code Style

- Ruff linter/formatter: target py313, line-length 110, rules: E, W, F, I, UP, B, SIM, TCH, RUF
- mypy strict mode (configured for core packages)
- Google-style docstrings
- Frozen dataclasses / Pydantic models for data
- Protocol-based design (Python Protocols for duck-typing, not ABCs)
- Async-first: async/await throughout

## Key Patterns

- **Error handling**: `AppError` with error codes, gRPC status mapping.
- **Config**: Pydantic Settings with env var loading.
- **Lifecycle**: Component protocol with `start/stop/health`, Registry ordering.
- **Provider**: `RequestResponse`, `Stream`, `Sink`, `Duplex` protocols.
- **Pipeline**: Async pull-based iterators with composable operators.
