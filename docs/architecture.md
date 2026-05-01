# pykit Architecture

pykit is organized as a **uv workspace monorepo** with 55+ independently installable sub-packages.
Lower layers never import higher ones — enforced via [`import-linter`](https://import-linter.readthedocs.io/).

## Layer Model

```
Layer 10 — Platform / Specialist
  pykit-agent · pykit-discovery · pykit-workload · pykit-process
  pykit-testutil · pykit-metrics · pykit-integration

Layer 9 — AI / ML
  pykit-llm · pykit-triton · pykit-bench · pykit-dataset
  pykit-transcription · pykit-embedding · pykit-vector-store
  pykit-llm-providers · pykit-explain

Layer 8 — Servers
  pykit-server · pykit-grpc · pykit-server-middleware · pykit-kafka-middleware

Layer 7 — Infrastructure Clients
  pykit-database · pykit-redis · pykit-storage · pykit-messaging · pykit-httpclient

Layer 6 — Security
  pykit-auth · pykit-authz · pykit-security · pykit-auth-oidc · pykit-auth-apikey

Layer 5 — Data & Flow
  pykit-pipeline · pykit-dag · pykit-worker · pykit-sse · pykit-stateful

Layer 4 — Core Patterns
  pykit-di · pykit-bootstrap · pykit-observability · pykit-hook
  pykit-mcp · pykit-chain

Layer 3 — Abstractions
  pykit-provider · pykit-component · pykit-resilience · pykit-schema

Layer 2 — Utilities
  pykit-validation · pykit-encryption · pykit-util · pykit-version · pykit-media

Layer 1 — Foundation
  pykit-errors · pykit-config · pykit-logging
```

## Key Principles

- **No upward imports** — a package may only import from the same or lower layers.
- **Protocol-first** — public contracts are `Protocol` classes, not concrete types.
- **Async throughout** — all I/O APIs are `async`/`await`.
- **Pydantic models** for all data exchange at layer boundaries.
- **Sibling parity** — public abstractions mirror [gokit](https://github.com/kbukum/gokit) (Go) and [rskit](https://github.com/kbukum/rskit) (Rust).

## Architecture Decision Records

See [`docs/adr/`](adr/) for the full list of ADRs.
The foundational decision is [ADR 0001 — Layered package architecture](adr/0001-layered-package-architecture.md).

## Further Reading

- [`docs/PACKAGES.md`](PACKAGES.md) — per-package descriptions and status
