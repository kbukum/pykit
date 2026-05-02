# 0001. Layered package architecture

- Status: Accepted
- Date: 2026-04-26
- Authors: @kbukum

## Context

pykit is a uv workspace with 50+ packages. Without an enforced layering
rule, foundation packages (e.g. `pykit-errors`) could accidentally import
from higher layers (e.g. `pykit-server`), creating cycles and undermining
the modular distribution model. The sibling repos
([`gokit`](https://github.com/kbukum/gokit),
[`rskit`](https://github.com/kbukum/rskit)) faced the same problem and
adopted three- or four-tier layering enforced by linters
(`depguard`/`cargo-deny`).

We need a stable rule that engineers can apply without case-by-case
debate, enforced automatically.

## Decision

We will organize pykit packages into the following layers (lowest depends
on nothing higher):

1. **Foundation** — `pykit-errors`, `pykit-config`, `pykit-logging`
2. **Utilities** — `pykit-validation`, `pykit-encryption`, `pykit-util`,
   `pykit-version`, `pykit-media`
3. **Patterns** — `pykit-provider`, `pykit-component`, `pykit-resilience`
4. **Frameworks** — `pykit-di`, `pykit-bootstrap`, `pykit-observability`
5. **Data & Flow** — `pykit-pipeline`, `pykit-dag`, `pykit-worker`,
   `pykit-sse`, `pykit-stateful`
6. **Security** — `pykit-auth`, `pykit-authz`, `pykit-security`
7. **Infrastructure** — `pykit-database`, `pykit-cache`, `pykit-storage`,
   `pykit-messaging`, `pykit-httpclient`
8. **Servers** — `pykit-server`, `pykit-grpc`
9. **AI/ML** — `pykit-llm`, `pykit-llm-providers`, `pykit-bench`,
   `pykit-dataset`
10. **Platform** — `pykit-discovery`, `pykit-workload`, `pykit-process`,
    `pykit-testutil`

When a foundation package needs a service that lives in a higher layer
(e.g. an HTTP transport for an SSE broadcaster), the foundation declares
a **Protocol** for the operation it needs. Higher-layer types satisfy it
structurally — no import flows downward.

The layer contract is enforced by [`import-linter`](https://import-linter.readthedocs.io/)
in `pyproject.toml` under `[tool.importlinter]`. CI runs
`uv run lint-imports` and fails the build on violations.

## Consequences

- New packages must be placed in the correct layer; the lint rule fails CI
  if violated.
- Cross-layer wiring lives in `pykit-bootstrap` and `pykit-di`; foundation
  packages remain independently testable and reusable.
- A small upfront cost: foundation packages duplicate single-method
  Protocols (e.g. `worker.Broadcaster`) instead of importing concrete
  transport types. This is a deliberate tradeoff for layering isolation.
- Sibling parity: the same layering decision exists in
  [`gokit/docs/adr/0001`](https://github.com/kbukum/gokit/blob/main/docs/adr/0001-three-tier-layering.md)
  and [`rskit/docs/adr/0001`](https://github.com/kbukum/rskit/blob/main/docs/adr/0001-layered-crate-architecture.md);
  changes here should be evaluated for both.

## Alternatives considered

- **No layering (status quo)** — relied on convention; review showed it
  doesn't hold at this package count.
- **Three tiers (foundation / patterns / everything else)** — too coarse
  for 50+ packages; "everything else" would still need internal ordering.
- **Per-package allowlists** — too brittle; every new package would require
  bilateral edits.
- **Move enforcement to runtime** — slows test startup and only catches
  exercised code paths.
