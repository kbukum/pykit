# Changelog

## [Unreleased]

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

## 0.1.0 — Initial Release

- Extracted from sentinel/py-services/pykit/
- Set up uv workspace with per-package structure
