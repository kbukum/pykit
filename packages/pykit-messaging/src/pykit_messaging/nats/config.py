"""NATS adapter configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from pykit_errors import AppError
from pykit_messaging.config import (
    BrokerConfig,
    CommitStrategy,
    DeliveryGuarantee,
    reject_exactly_once,
    validate_topic_name,
)

BACKEND_NAME = "nats"
DEFAULT_URL = "tls://localhost:4222"


@dataclass
class NatsConfig(BrokerConfig):
    """Configuration for the core NATS adapter."""

    backend: str = BACKEND_NAME
    name: str = BACKEND_NAME
    delivery_guarantee: DeliveryGuarantee = DeliveryGuarantee.AT_MOST_ONCE
    commit_strategy: CommitStrategy = CommitStrategy.AUTO

    url: str = field(default=DEFAULT_URL, repr=False)
    brokers: list[str] = field(default_factory=list, repr=False)
    subject_prefix: str = ""
    queue_group: str = ""
    connect_timeout: float = 2.0
    drain_timeout: float = 2.0
    reconnect_time_wait: float = 2.0
    allow_reconnect: bool = True
    token: str = field(default="", repr=False)
    username: str = field(default="", repr=False)
    password: str = field(default="", repr=False)
    allow_insecure_dev: bool = False

    def validate(self) -> None:
        """Validate NATS-specific and broker-neutral settings."""
        super().validate()
        reject_exactly_once(self, BACKEND_NAME)
        if self.delivery_guarantee is not DeliveryGuarantee.AT_MOST_ONCE:
            raise AppError.invalid_input(
                "delivery_guarantee", "core NATS subjects support at-most-once delivery only"
            )
        if self.commit_strategy is not CommitStrategy.AUTO:
            raise AppError.invalid_input("commit_strategy", "core NATS subjects do not support manual acks")
        if not self.servers():
            raise AppError.invalid_input("brokers", "at least one NATS server URL is required")
        for server in self.servers():
            _validate_server_url(server, self.allow_insecure_dev)
        if self.subject_prefix:
            validate_topic_name(self.subject_prefix.strip("."), "subject_prefix")
        if self.queue_group:
            validate_topic_name(self.queue_group, "queue_group")
        if self.connect_timeout <= 0:
            raise AppError.invalid_input("connect_timeout", "connect_timeout must be greater than 0")
        if self.drain_timeout < 0:
            raise AppError.invalid_input("drain_timeout", "drain_timeout must be greater than or equal to 0")
        if self.reconnect_time_wait < 0:
            raise AppError.invalid_input(
                "reconnect_time_wait", "reconnect_time_wait must be greater than or equal to 0"
            )
        if self.token and (self.username or self.password):
            raise AppError.invalid_input("auth", "NATS token auth cannot be combined with username/password")
        if bool(self.username) != bool(self.password):
            raise AppError.invalid_input("auth", "NATS username and password must be provided together")

    def servers(self) -> list[str]:
        """Return configured NATS server URLs."""
        return [server for server in (self.brokers or [self.url]) if server]

    def subject(self, topic: str) -> str:
        """Return topic with the configured subject prefix applied."""
        validate_topic_name(topic, "topic")
        if not self.subject_prefix:
            return topic
        return f"{self.subject_prefix.rstrip('.')}.{topic.lstrip('.')}"


def _validate_server_url(value: str, allow_insecure_dev: bool) -> None:
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.hostname:
        raise AppError.invalid_input("brokers", "NATS server URL must include a scheme and host")
    if parsed.username or parsed.password:
        raise AppError.invalid_input(
            "brokers", "NATS credentials must be configured via token or username/password, not URL userinfo"
        )
    if parsed.query:
        raise AppError.invalid_input("brokers", "NATS server URL query strings are not accepted")
    if parsed.scheme not in {"tls", "wss"} and not allow_insecure_dev:
        raise AppError.invalid_input("brokers", "NATS plaintext URLs require allow_insecure_dev=True")
