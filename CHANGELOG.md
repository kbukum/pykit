# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — Documentation & Project Hygiene
- `CODE_OF_CONDUCT.md` — Contributor Covenant v2.1 (cross-sibling parity).
- `SECURITY.md` — vulnerability disclosure policy, supply-chain section
  (Sigstore Trusted Publishing, CycloneDX SBOM, `pip-audit`).
- `GOVERNANCE.md` — roles, decision making, sibling-parity contract.
- `MAINTAINERS.md` — current maintainers, areas, succession.
- `docs/RELEASING.md` — mechanical release process for the uv workspace.
- `docs/VERSIONING.md` — workspace versioning guide.
- `docs/policy/SEMVER.md` — semantic-versioning policy (PEP 440 aware).
- `docs/policy/DEPRECATION.md` — deprecation lifecycle (PEP 702 `@deprecated`).
- `docs/adr/0000-template.md` and `docs/adr/0001-layered-package-architecture.md` —
  Architecture Decision Records.
- `.github/CODEOWNERS` — review ownership across all packages.
- `.github/dependabot.yml` — pip + GitHub Actions dependency automation.
- `.github/PULL_REQUEST_TEMPLATE.md` — PR checklist with sibling-parity prompt.
- `.github/ISSUE_TEMPLATE/{bug_report,feature_request,config}.yml` — modern
  YAML form templates.
- README: sibling-projects callout and `Project Documentation` index.

### Added — Cross-Kit Alignment

- **pykit-errors**: `ErrorCode` enum with 17 standardized codes, fluent error builders, RFC 7807 `ErrorResponse` support
- **pykit-config**: `AppConfig` Protocol, `ServiceConfig`, `LoggingConfig`, `Environment` enum
- **pykit-bootstrap**: `on_configure` hooks, `Component` integration for lifecycle management
- **pykit-discovery**: `ServiceInstance` enrichment, `LeastConnectionsStrategy` for load balancing
- **pykit-observability**: `ServiceHealth`, `ComponentHealth`, `HealthStatus` types
- **pykit-server**: `BaseServer` `Component` protocol implementation

### Added — Project Infrastructure

- **LICENSE**: MIT license file
- **CONTRIBUTING.md**: Development setup, code style, testing, PR process guidelines
- **All packages**: Added `description` field to all 44 `pyproject.toml` files
- **README.md**: Added badges, contributing section, code of conduct, updated package descriptions

### Breaking Changes
- **pykit-kafka → pykit-messaging**: The `pykit-kafka` package has been replaced by `pykit-messaging`
  - Abstract protocols (`MessageProducer`, `MessageConsumer`, `Message`, `Event`) in `pykit_messaging`
  - Kafka implementation in `pykit_messaging.kafka` sub-package
  - New `InMemoryBroker` in `pykit_messaging.memory` for testing
  - Install with `pykit-messaging[kafka]` for Kafka support
  - Old `pykit-kafka` package has been removed

### Migration
- `from pykit_kafka import ...` → `from pykit_messaging import ...` (for types)
- `from pykit_kafka import KafkaProducer` → `from pykit_messaging.kafka import KafkaProducer`
- Dependency: `pykit-kafka` → `pykit-messaging[kafka]`

### Added — Messaging Enhancement

- **pykit-messaging**: `ManagedProducer` — wraps any `MessageProducer` with lifecycle (start/stop), metrics collection, and running state
- **pykit-messaging**: `ManagedConsumer` — wraps any `MessageConsumer` with lifecycle, handler dispatch, and graceful shutdown
- **pykit-messaging**: `ConsumerRunner` — asyncio task management for consumption loops
- **pykit-messaging**: `MetricsCollector` protocol with `record_publish()`/`record_consume()` and `NoopMetrics` impl
- **pykit-messaging**: `MessageTranslator` protocol with `JsonTranslator` implementation
- **pykit-messaging**: `MessageHandlerProtocol` + `FuncHandler` adapter + `HandlerMiddleware` type + `chain_handlers()`
- **pykit-messaging**: `MessageRouter` — topic routing with wildcard pattern support (fnmatch) and default handler
- **pykit-messaging**: `BatchProducer` — buffered producer with size, time (periodic flush), and byte flush triggers
- **pykit-messaging**: Provider bridge:
  - `ProducerSink` — wraps `MessageProducer` as `Sink[Message]`
  - `ConsumerStream` — wraps `MessageConsumer` as `Stream[None, Message]`
- **pykit-messaging**: Middleware:
  - `DedupMiddleware` — deduplication with sliding window (size + TTL) using OrderedDict
  - `CircuitBreakerMiddleware` — fail-fast with CLOSED/OPEN/HALF_OPEN states
- **pykit-messaging**: Enhanced `InMemoryBroker` with message history, topic tracking, and reset
- **pykit-messaging**: Test assertions — `assert_published()`, `assert_published_n()`, `assert_no_messages()`, `wait_for_message()`

## 0.1.0 — Initial Release

- Extracted from sentinel/py-services/pykit/
- Set up uv workspace with per-package structure
