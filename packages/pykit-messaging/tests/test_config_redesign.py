from __future__ import annotations

from collections.abc import Callable

import pytest

from pykit_errors import AppError
from pykit_messaging import (
    BrokerConfig,
    CommitStrategy,
    DeliveryGuarantee,
    DLQPolicy,
    MemoryConfig,
    MessagingRegistry,
)
from pykit_messaging.kafka import KafkaConfig
from pykit_messaging.kafka import register as register_kafka
from pykit_messaging.memory import register as register_memory
from pykit_messaging.nats import NatsConfig
from pykit_messaging.nats import register as register_nats
from pykit_messaging.rabbitmq import RabbitMqConfig
from pykit_messaging.rabbitmq import register as register_rabbitmq


def test_core_broker_config_contains_only_shared_policy_and_defaults() -> None:
    cfg = BrokerConfig(adapter="  memory  ", name="")

    assert cfg.adapter == "memory"
    assert cfg.name == "memory"
    assert cfg.enabled is True
    assert cfg.delivery_guarantee is DeliveryGuarantee.AT_LEAST_ONCE
    assert cfg.commit_strategy is CommitStrategy.POST_HANDLER_SUCCESS
    assert cfg.dlq == DLQPolicy()
    assert cfg.max_in_flight == 1
    assert cfg.request_timeout_ms == 30000
    assert cfg.retries == 3
    assert not hasattr(cfg, "brokers")
    assert cfg.consumer_group == ""
    assert cfg.topics == []
    assert cfg.subscriptions == []


@pytest.mark.parametrize(
    ("kwargs", "field"),
    [
        ({"adapter": ""}, "adapter"),
        ({"max_in_flight": 0}, "max_in_flight"),
        ({"retries": -1}, "retries"),
        ({"request_timeout_ms": 0}, "request_timeout_ms"),
        ({"retry_backoff_ms": -1}, "retry_backoff_ms"),
    ],
)
def test_core_broker_config_validation(kwargs: dict[str, object], field: str) -> None:
    with pytest.raises(AppError) as exc_info:
        BrokerConfig(**kwargs)

    assert exc_info.value.details["field"] == field


def test_dlq_policy_validation() -> None:
    with pytest.raises(AppError) as exc_info:
        DLQPolicy(enabled=True, suffix="")

    assert exc_info.value.details["field"] == "dlq.suffix"


def test_kafka_config_validation_and_secret_redaction() -> None:
    cfg = KafkaConfig(
        security_protocol="SASL_SSL",
        sasl_mechanism="PLAIN",
        sasl_username="user-secret",
        sasl_password="password-secret",
        transactional_id="txn-secret",
    )

    rendered = repr(cfg)
    assert "user-secret" not in rendered
    assert "password-secret" not in rendered
    assert "txn-secret" not in rendered
    assert cfg.brokers == ["localhost:9092"]


def test_kafka_exactly_once_is_rejected_until_transactions_are_supported() -> None:
    with pytest.raises(AppError) as exc_info:
        KafkaConfig(delivery_guarantee=DeliveryGuarantee.EXACTLY_ONCE)

    assert exc_info.value.details["field"] == "delivery_guarantee"


def test_nats_config_validation_defaults_and_secret_redaction() -> None:
    cfg = NatsConfig(
        token="token-secret",
        url="tls://broker:4222",
        brokers=["tls://broker:4222"],
    )

    rendered = repr(cfg)
    assert cfg.delivery_guarantee is DeliveryGuarantee.AT_MOST_ONCE
    assert cfg.commit_strategy is CommitStrategy.AUTO
    assert cfg.subject("events") == "events"
    assert "token-secret" not in rendered
    assert "url=" not in rendered
    assert "brokers=" not in rendered
    assert "token=" not in rendered


def test_nats_rejects_ack_based_shared_semantics() -> None:
    with pytest.raises(AppError) as exc_info:
        NatsConfig(delivery_guarantee=DeliveryGuarantee.AT_LEAST_ONCE)

    assert exc_info.value.details["field"] == "delivery_guarantee"


def test_rabbitmq_config_validation_defaults_and_secret_redaction() -> None:
    cfg = RabbitMqConfig(url="amqps://broker:5671/", username="user-secret", password="password-secret")

    rendered = repr(cfg)
    assert cfg.delivery_guarantee is DeliveryGuarantee.AT_LEAST_ONCE
    assert cfg.commit_strategy is CommitStrategy.POST_HANDLER_SUCCESS
    assert cfg.auto_ack is False
    assert cfg.routing_key("events") == "events"
    assert "user-secret" not in rendered
    assert "password-secret" not in rendered
    assert "url=" not in rendered


def test_rabbitmq_auto_ack_must_align_with_commit_strategy() -> None:
    with pytest.raises(AppError) as exc_info:
        RabbitMqConfig(auto_ack=True, commit_strategy=CommitStrategy.POST_HANDLER_SUCCESS)

    assert exc_info.value.details["field"] == "commit_strategy"


def test_adapter_configs_reject_plaintext_without_dev_opt_in_and_url_credentials() -> None:
    with pytest.raises(AppError):
        KafkaConfig(security_protocol="PLAINTEXT")
    assert (
        KafkaConfig(security_protocol="PLAINTEXT", allow_insecure_dev=True).security_protocol == "PLAINTEXT"
    )

    with pytest.raises(AppError):
        NatsConfig(url="nats://broker:4222")
    assert NatsConfig(url="nats://broker:4222", allow_insecure_dev=True).url == "nats://broker:4222"
    with pytest.raises(AppError):
        NatsConfig(url="tls://token-secret@broker:4222")

    with pytest.raises(AppError):
        RabbitMqConfig(url="amqp://broker:5672/")
    assert RabbitMqConfig(url="amqp://broker:5672/", allow_insecure_dev=True).url == "amqp://broker:5672/"
    with pytest.raises(AppError):
        RabbitMqConfig(url="amqps://user-secret:password-secret@broker:5671/")


def test_adapter_configs_reject_invalid_dynamic_names() -> None:
    with pytest.raises(AppError):
        KafkaConfig(topics=["bad topic"])
    with pytest.raises(AppError):
        NatsConfig(subject_prefix="bad/subject")
    with pytest.raises(AppError):
        RabbitMqConfig(queue_name="bad queue")


def test_memory_config_preserves_bounded_settings_and_rejects_invalid_values() -> None:
    cfg = MemoryConfig(capacity=8, history_limit=16, max_brokers=2)

    assert cfg.capacity == 8
    assert cfg.history_limit == 16
    assert cfg.max_brokers == 2
    with pytest.raises(AppError) as exc_info:
        MemoryConfig(history_limit=0)
    assert exc_info.value.details["field"] == "history_limit"


@pytest.mark.parametrize(
    "adapter,register",
    [
        ("memory", register_memory),
        ("kafka", register_kafka),
        ("nats", register_nats),
        ("rabbitmq", register_rabbitmq),
    ],
)
def test_factories_reject_unsupported_exactly_once_from_core_config(
    adapter: str, register: Callable[[MessagingRegistry], None]
) -> None:
    registry = MessagingRegistry()
    register(registry)

    with pytest.raises(AppError) as exc_info:
        registry.producer(BrokerConfig(adapter=adapter, delivery_guarantee=DeliveryGuarantee.EXACTLY_ONCE))

    assert exc_info.value.details["field"] in {"delivery_guarantee", "transactional_id"}


def test_registry_rejects_disabled_creation_time_config() -> None:
    registry = MessagingRegistry()
    register_memory(registry)

    with pytest.raises(AppError) as exc_info:
        registry.producer(MemoryConfig(enabled=False))

    assert exc_info.value.details["field"] == "enabled"
