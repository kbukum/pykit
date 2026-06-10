# pykit

Python infrastructure toolkit providing foundational packages for service development. Mirrors gokit (Go) and rskit (Rust) in module structure and naming.

## Engineering principles

Shared engineering baseline — apply to all work here:

- **Phases:** discover → decide (Redesign / Align / Enhance / Drop / Leave) → implement completely → validate. Prefer root-cause redesign over symptom patches; no compatibility shims in pre-stable code.
- **Layering & reuse:** explicit, acyclic dependency direction — lower layers never import higher. Reuse or enhance the canonical owner before writing new code; never duplicate shared concerns (errors, config, logging, auth, retries, observability, HTTP, registries).
- **APIs:** typed and minimal; no broad `Any` / `interface{}` / unchecked `unknown` in public surfaces; actionable typed errors that preserve cause.
- **Errors & resilience:** no panics / unwrap or swallowed errors on runtime paths; no success-shaped fallbacks; timeout every remote call; bounded jittered retries for idempotent ops only; circuit-break and degrade gracefully.
- **Concurrency:** every task has ownership, cancellation, timeout, and shutdown; bound queues / buffers / concurrency with documented backpressure; drain on shutdown.
- **Security & privacy:** validate at every trust boundary; least-privilege and secure-by-default; parameterized queries and argv-only subprocess; tokens in headers, not query strings; current crypto only; minimize, redact, and retention-bound sensitive data.
- **Composition:** explicit injected registries and config-driven selection; no import-time side effects, no mutable global registries; inject logger / tracer / policies rather than reaching for globals.
- **Tests:** behavioral and deterministic; race / shuffle / parallel green; cover failure paths; fixtures over embedded config; regression-test every fix.
- **AI / model features:** treat model output and retrieved context as untrusted; enforce structured outputs; least-privilege tool calls with a human gate on destructive actions; version prompts / models and gate changes on evals.
- **Supply chain:** pin CI actions by SHA; scan dependencies (vulnerabilities + licenses); sign release artifacts; attach SBOM and provenance.
- **Currency:** use current idioms and standards, not folklore — verify the dependency is maintained, the stdlib doesn't already cover it, and no open CVE applies.

## Build, Test, and Lint

Requires: Python 3.13+, uv.

```bash
uv sync                              # Install all dependencies
uv run pytest                        # Run all tests
uv run pytest --cov                  # Run tests with coverage (minimum 60%)
uv run ruff check core/packages/ contrib/
uv run ruff format core/packages/ contrib/
uv run mypy                          # Type check (strict mode)
uv run import-linter                 # Verify layer architecture compliance
```

## Package Structure

uv workspace monorepo with foundation packages in `core/packages/` and flat contrib adapter packages in `contrib/`. Each package has its own `pyproject.toml`.

The root `pykit` package is a lazy-loading facade that re-exports all sub-packages.

**Layers** (enforced by import-linter — lower layers must not import higher):

| Layer | Packages |
|-------|----------|
| Foundation | errors, config, logging |
| Core | validation, encryption, util, version, media |
| Component | component, provider, resilience |
| Infrastructure | di, bootstrap, pipeline, dag, observability |
| Adapters | database, cache, storage, kafka, httpclient |
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
