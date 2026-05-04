"""RabbitMQ adapter configuration."""

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

ADAPTER_NAME = "rabbitmq"
DEFAULT_URL = "amqps://localhost:5671/"
EXCHANGE_TYPES = {"direct", "fanout", "topic", "headers"}


@dataclass
class RabbitMqConfig(BrokerConfig):
    """Configuration for the RabbitMQ adapter."""

    adapter: str = ADAPTER_NAME
    name: str = ADAPTER_NAME
    url: str = field(default=DEFAULT_URL, repr=False)
    routing_key_prefix: str = ""
    exchange_name: str = ""
    exchange_type: str = "direct"
    queue_name: str = ""
    durable: bool = True
    auto_delete: bool = False
    exclusive: bool = False
    auto_ack: bool = False
    publisher_confirms: bool = True
    connection_name: str = ""
    username: str = field(default="", repr=False)
    password: str = field(default="", repr=False)
    allow_insecure_dev: bool = False

    def validate(self) -> None:
        """Validate RabbitMQ-specific and broker-neutral settings."""
        super().validate()
        reject_exactly_once(self, ADAPTER_NAME)
        if not self.url:
            raise AppError.invalid_input("url", "RabbitMQ connection URL is required")
        _validate_rabbitmq_url(self.url, self.allow_insecure_dev)
        if self.routing_key_prefix:
            validate_topic_name(self.routing_key_prefix.strip("."), "routing_key_prefix")
        if self.queue_name:
            validate_topic_name(self.queue_name, "queue_name")
        if self.exchange_name:
            validate_topic_name(self.exchange_name, "exchange_name")
        if self.exchange_type not in EXCHANGE_TYPES:
            raise AppError.invalid_input("exchange_type", "unsupported RabbitMQ exchange type")
        if self.auto_ack and self.commit_strategy is not CommitStrategy.AUTO:
            raise AppError.invalid_input("commit_strategy", "auto_ack requires commit_strategy=auto")
        if not self.auto_ack and self.commit_strategy is CommitStrategy.AUTO:
            raise AppError.invalid_input("auto_ack", "commit_strategy=auto requires auto_ack=True")
        if self.delivery_guarantee is DeliveryGuarantee.AT_MOST_ONCE and not self.auto_ack:
            raise AppError.invalid_input("auto_ack", "at-most-once delivery requires auto_ack=True")
        if self.delivery_guarantee is DeliveryGuarantee.AT_LEAST_ONCE and self.auto_ack:
            raise AppError.invalid_input(
                "auto_ack", "at-least-once delivery requires explicit ack after handling"
            )
        if self.exclusive and self.durable:
            raise AppError.invalid_input("exclusive", "exclusive RabbitMQ queues cannot be durable")
        if bool(self.username) != bool(self.password):
            raise AppError.invalid_input("auth", "RabbitMQ username and password must be provided together")

    def routing_key(self, topic: str) -> str:
        """Return topic with the configured routing key prefix applied."""
        validate_topic_name(topic, "topic")
        if not self.routing_key_prefix:
            return topic
        return f"{self.routing_key_prefix.rstrip('.')}.{topic.lstrip('.')}"

    def queue_for(self, topic: str) -> str:
        """Return the queue name for a subscribed topic."""
        return self.queue_name or self.routing_key(topic)


def _validate_rabbitmq_url(value: str, allow_insecure_dev: bool) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"amqp", "amqps"} or not parsed.hostname:
        raise AppError.invalid_input("url", "RabbitMQ URL must include amqp/amqps scheme and host")
    if parsed.username or parsed.password:
        raise AppError.invalid_input(
            "url", "RabbitMQ credentials must be configured via username/password, not URL userinfo"
        )
    if parsed.query:
        raise AppError.invalid_input("url", "RabbitMQ URL query strings are not accepted")
    if parsed.scheme != "amqps" and not allow_insecure_dev:
        raise AppError.invalid_input("url", "RabbitMQ plaintext URLs require allow_insecure_dev=True")
