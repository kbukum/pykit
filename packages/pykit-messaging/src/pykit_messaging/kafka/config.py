"""Kafka configuration extending the broker-agnostic base."""

from __future__ import annotations

from dataclasses import dataclass, field

from pykit_messaging.config import BrokerConfig


@dataclass
class KafkaConfig(BrokerConfig):
    """Configuration for Kafka producer/consumer.

    Inherits :class:`~pykit_messaging.config.BrokerConfig` fields
    (``name``, ``enabled``, ``brokers``, ``retries``, ``request_timeout_ms``)
    and adds Kafka-specific settings.
    """

    # Override defaults for Kafka
    name: str = "kafka"
    brokers: list[str] = field(default_factory=lambda: ["localhost:9092"])

    # Kafka-specific fields
    group_id: str = ""
    topics: list[str] = field(default_factory=list)

    # Security
    security_protocol: str = "PLAINTEXT"
    sasl_mechanism: str = ""
    sasl_username: str = ""
    sasl_password: str = ""

    # Producer settings
    compression_type: str = "snappy"
    max_batch_size: int = 16384
    retry_backoff_ms: int = 100

    # Consumer settings
    session_timeout_ms: int = 30000
    heartbeat_interval_ms: int = 3000
    auto_offset_reset: str = "earliest"
