"""Broker-agnostic messaging configuration."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Self

from pykit_errors import AppError

_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_TOPIC_RE = re.compile(r"^[A-Za-z0-9._:-]+$")


class DeliveryGuarantee(StrEnum):
    """Requested broker delivery semantics."""

    AT_MOST_ONCE = "at_most_once"
    AT_LEAST_ONCE = "at_least_once"
    EXACTLY_ONCE = "exactly_once"


class CommitStrategy(StrEnum):
    """Offset/ack commit behavior."""

    AUTO = "auto"
    POST_HANDLER_SUCCESS = "post_handler_success"
    MANUAL = "manual"


@dataclass(frozen=True)
class DLQPolicy:
    """Dead-letter queue policy shared across broker adapters."""

    enabled: bool = True
    suffix: str = ".dlq"

    def __post_init__(self) -> None:
        if self.enabled and not self.suffix:
            raise AppError.invalid_input("dlq.suffix", "DLQ suffix is required when DLQ is enabled")


@dataclass
class BrokerConfig:
    """Base configuration shared by all broker adapters.

    Core config intentionally contains only broker-neutral policy, including
    topic/subscription names when a caller wants an adapter-neutral selection.
    Adapter modules own connection endpoints, protocol security, batching, and
    broker-specific timeouts.
    """

    adapter: str = "memory"
    name: str = ""
    enabled: bool = True
    delivery_guarantee: DeliveryGuarantee = DeliveryGuarantee.AT_LEAST_ONCE
    commit_strategy: CommitStrategy = CommitStrategy.POST_HANDLER_SUCCESS
    dlq: DLQPolicy = field(default_factory=DLQPolicy)
    max_in_flight: int = 1
    consumer_group: str = ""
    topics: list[str] = field(default_factory=list)
    subscriptions: list[str] = field(default_factory=list)
    retries: int = 3
    request_timeout_ms: int = 30000
    retry_backoff_ms: int = 100

    def __post_init__(self) -> None:
        self.apply_defaults()
        self.validate()

    def apply_defaults(self) -> Self:
        """Normalize broker-neutral default values in-place and return ``self``."""
        self.adapter = self.adapter.strip()
        self.name = self.name.strip() or self.adapter
        self.consumer_group = self.consumer_group.strip()
        try:
            self.delivery_guarantee = DeliveryGuarantee(self.delivery_guarantee)
        except ValueError as exc:
            raise AppError.invalid_input("delivery_guarantee", "unsupported delivery guarantee") from exc
        try:
            self.commit_strategy = CommitStrategy(self.commit_strategy)
        except ValueError as exc:
            raise AppError.invalid_input("commit_strategy", "unsupported commit strategy") from exc
        if self.commit_strategy is CommitStrategy.MANUAL:
            raise AppError.invalid_input(
                "commit_strategy",
                "manual commits require an explicit ack/commit API and are not supported yet",
            )
        return self

    def validate(self) -> None:
        """Validate broker-neutral configuration fields."""
        if not self.adapter:
            raise AppError.invalid_input("adapter", "messaging adapter name is required")
        if not _NAME_RE.fullmatch(self.adapter):
            raise AppError.invalid_input(
                "adapter", "messaging adapter must contain only letters, digits, ., _, or -"
            )
        if not _NAME_RE.fullmatch(self.name):
            raise AppError.invalid_input(
                "name", "messaging config name must contain only letters, digits, ., _, or -"
            )
        if self.max_in_flight < 1:
            raise AppError.invalid_input("max_in_flight", "max_in_flight must be at least 1")
        for topic in self.topics:
            validate_topic_name(topic, "topics")
        for subscription in self.subscriptions:
            validate_topic_name(subscription, "subscriptions")
        if self.consumer_group:
            validate_topic_name(self.consumer_group, "consumer_group")
        if self.retries < 0:
            raise AppError.invalid_input("retries", "retries must be greater than or equal to 0")
        if self.request_timeout_ms < 1:
            raise AppError.invalid_input("request_timeout_ms", "request_timeout_ms must be at least 1")
        if self.retry_backoff_ms < 0:
            raise AppError.invalid_input(
                "retry_backoff_ms", "retry_backoff_ms must be greater than or equal to 0"
            )


def reject_exactly_once(config: BrokerConfig, adapter: str) -> None:
    """Raise a typed config error when *adapter* cannot provide exactly-once delivery."""
    if config.delivery_guarantee is DeliveryGuarantee.EXACTLY_ONCE:
        raise AppError.invalid_input(
            "delivery_guarantee",
            f"{adapter} does not support exactly-once delivery with this adapter",
        )


def _validate_topic_like(field: str, value: str) -> None:
    if not value or any(ch.isspace() or ord(ch) < 32 for ch in value):
        raise AppError.invalid_input(
            field, f"{field} entries must not be empty or contain whitespace/control characters"
        )


def validate_topic_name(value: str, field: str = "topic") -> None:
    """Validate broker-neutral topic, subject, queue, and group names."""
    if not value or not value.strip():
        raise AppError.invalid_input(field, f"{field} is required")
    if len(value) > 249:
        raise AppError.invalid_input(field, f"{field} must be at most 249 bytes")
    if not _TOPIC_RE.fullmatch(value):
        raise AppError.invalid_input(field, f"{field} must contain only letters, digits, ., _, -, or :")
    if ".." in value:
        raise AppError.invalid_input(field, f"{field} must not contain empty path segments")
