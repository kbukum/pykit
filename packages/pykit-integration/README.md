# pykit-integration

Cross-layer integration tests for the pykit monorepo.

## Usage

This package is not intended for installation as a user dependency.
It provides integration test suites that exercise interactions across multiple pykit packages.

## Running the tests

```bash
uv run pytest packages/pykit-integration/
```

## What it tests

- Full bootstrap lifecycle: config → logging → DI container → component start/stop
- Auth pipeline: validation → JWT issuance → RBAC authorization
- Pipeline + resilience: composable stages with retry and circuit breaker
- Error propagation: `AppError` across gRPC, HTTP, and logging boundaries

## Features

- End-to-end scenarios spanning Foundation → Core → Infrastructure layers
- In-memory fakes and stubs for external dependencies (Redis, DB, Kafka)
- Async pytest fixtures with proper lifecycle management
