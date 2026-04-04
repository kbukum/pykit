"""Kafka configuration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class KafkaConfig:
    """Configuration for Kafka producer/consumer."""

    name: str = "kafka"
    brokers: list[str] = field(default_factory=lambda: ["localhost:9092"])
    group_id: str = ""
    topics: list[str] = field(default_factory=list)
    enabled: bool = True

    # Security
    security_protocol: str = "PLAINTEXT"
    sasl_mechanism: str = ""
    sasl_username: str = ""
    sasl_password: str = ""

    # Producer settings
    compression_type: str = "snappy"
    max_batch_size: int = 16384
    request_timeout_ms: int = 30000
    retry_backoff_ms: int = 100

    # Consumer settings
    session_timeout_ms: int = 30000
    heartbeat_interval_ms: int = 3000
    auto_offset_reset: str = "earliest"
