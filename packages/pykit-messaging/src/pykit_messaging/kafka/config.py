"""Kafka configuration extending the broker-agnostic base."""

from __future__ import annotations

from dataclasses import dataclass, field

from pykit_errors import AppError
from pykit_messaging.config import (
    BrokerConfig,
    reject_exactly_once,
    validate_topic_name,
)

_SECURITY_PROTOCOLS = {"PLAINTEXT", "SSL", "SASL_PLAINTEXT", "SASL_SSL"}
_COMPRESSION_TYPES = {"gzip", "snappy", "lz4", "zstd", "none"}
_OFFSET_RESETS = {"earliest", "latest", "none"}
_ACKS = {"0", "1", "all"}


@dataclass
class KafkaConfig(BrokerConfig):
    """Configuration for the Kafka adapter."""

    backend: str = "kafka"
    name: str = "kafka"

    # Kafka connection and subscription settings.
    brokers: list[str] = field(default_factory=lambda: ["localhost:9092"])
    group_id: str = ""
    topics: list[str] = field(default_factory=list)

    # Security.
    security_protocol: str = "SSL"
    sasl_mechanism: str = ""
    sasl_username: str = field(default="", repr=False)
    sasl_password: str = field(default="", repr=False)
    ssl_context: object | None = field(default=None, repr=False)
    allow_insecure_dev: bool = False

    # Producer settings.
    compression_type: str = "snappy"
    max_batch_size: int = 16384
    linger_ms: int = 0
    acks: str = "all"
    enable_idempotence: bool = True
    transactional_id: str = field(default="", repr=False)

    # Consumer settings.
    session_timeout_ms: int = 30000
    heartbeat_interval_ms: int = 3000
    auto_offset_reset: str = "earliest"
    max_poll_records: int | None = None

    def validate(self) -> None:
        """Validate Kafka-specific and broker-neutral settings."""
        super().validate()
        if self.consumer_group and self.group_id and self.consumer_group != self.group_id:
            raise AppError.invalid_input(
                "consumer_group", "consumer_group and group_id must match when both are set"
            )
        if not self.brokers:
            raise AppError.invalid_input("brokers", "at least one Kafka bootstrap broker is required")
        if any(not broker.strip() for broker in self.brokers):
            raise AppError.invalid_input("brokers", "Kafka broker addresses must be non-empty")
        if any(_has_url_credentials(broker) or "?" in broker for broker in self.brokers):
            raise AppError.invalid_input(
                "brokers", "Kafka broker addresses must not contain credentials or query strings"
            )
        for topic in self.topics:
            validate_topic_name(topic, "topics")
        if self.group_id:
            validate_topic_name(self.group_id, "group_id")
        if self.security_protocol not in _SECURITY_PROTOCOLS:
            raise AppError.invalid_input("security_protocol", "unsupported Kafka security protocol")
        if self.security_protocol in {"PLAINTEXT", "SASL_PLAINTEXT"} and not self.allow_insecure_dev:
            raise AppError.invalid_input(
                "security_protocol", "Kafka plaintext protocols require allow_insecure_dev=True"
            )
        if self.security_protocol.startswith("SASL") and not self.sasl_mechanism:
            raise AppError.invalid_input("sasl_mechanism", "SASL Kafka connections require a mechanism")
        if self.sasl_mechanism and (not self.sasl_username or not self.sasl_password):
            raise AppError.invalid_input(
                "sasl_credentials", "SASL Kafka connections require username and password"
            )
        if self.compression_type not in _COMPRESSION_TYPES:
            raise AppError.invalid_input("compression_type", "unsupported Kafka compression type")
        if self.max_batch_size < 1:
            raise AppError.invalid_input("max_batch_size", "max_batch_size must be at least 1")
        if self.linger_ms < 0:
            raise AppError.invalid_input("linger_ms", "linger_ms must be greater than or equal to 0")
        if self.acks not in _ACKS:
            raise AppError.invalid_input("acks", "Kafka acks must be one of 0, 1, or all")
        if self.auto_offset_reset not in _OFFSET_RESETS:
            raise AppError.invalid_input("auto_offset_reset", "unsupported Kafka auto_offset_reset")
        if self.session_timeout_ms < 1:
            raise AppError.invalid_input("session_timeout_ms", "session_timeout_ms must be at least 1")
        if self.heartbeat_interval_ms < 1:
            raise AppError.invalid_input("heartbeat_interval_ms", "heartbeat_interval_ms must be at least 1")
        if self.heartbeat_interval_ms >= self.session_timeout_ms:
            raise AppError.invalid_input(
                "heartbeat_interval_ms", "heartbeat_interval_ms must be less than session_timeout_ms"
            )
        if self.max_poll_records is not None and self.max_poll_records < 1:
            raise AppError.invalid_input("max_poll_records", "max_poll_records must be at least 1")
        reject_exactly_once(self, "kafka")


def _has_url_credentials(value: str) -> bool:
    marker = "://"
    if marker not in value:
        return False
    authority = value.split(marker, 1)[1].split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    return "@" in authority
