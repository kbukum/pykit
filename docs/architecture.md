# pykit Architecture

pykit is organized as a **uv workspace monorepo** with 55+ independently installable sub-packages.
Lower layers never import higher ones — enforced via [`import-linter`](https://import-linter.readthedocs.io/).

## Layer Model

```
Layer 10 — Platform / Specialist
  pykit-agent · pykit-discovery · pykit-workload · pykit-process
  pykit-testutil · pykit-observability · pykit-integration

Layer 9 — AI / ML
  pykit-llm · pykit-inference · pykit-bench · pykit-dataset
  pykit-transcription · pykit-embedding · pykit-vectorstore
  pykit-llm-providers · pykit-explain

Layer 8 — Servers
  pykit-server · pykit-grpc · pykit-messaging

Layer 7 — Infrastructure Clients
  pykit-database · pykit-cache · pykit-storage · pykit-messaging · pykit-httpclient

Layer 6 — Security
  pykit-auth · pykit-authz · pykit-security

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

See [`docs/adr/`](adr/) for the ADR index. The current layer model is captured
in this document and summarized package-by-package in [`docs/PACKAGES.md`](PACKAGES.md).

## Further Reading

- [`docs/PACKAGES.md`](PACKAGES.md) — per-package descriptions and status
