"""RabbitMQ provider for pykit-messaging."""

from __future__ import annotations

from dataclasses import fields
from typing import TYPE_CHECKING

from pykit_messaging.config import BrokerConfig
from pykit_messaging.rabbitmq.config import ADAPTER_NAME, RabbitMqConfig
from pykit_messaging.rabbitmq.consumer import RabbitMqConsumer
from pykit_messaging.rabbitmq.producer import RabbitMqProducer

if TYPE_CHECKING:
    from pykit_messaging.registry import MessagingRegistry


def register(registry: MessagingRegistry) -> None:
    """Register config-free RabbitMQ producer and consumer factories."""
    registry.register_producer(ADAPTER_NAME, lambda config: RabbitMqProducer(_config_from(config)))
    registry.register_consumer(ADAPTER_NAME, lambda config: RabbitMqConsumer(_config_from(config)))


def _config_from(config: BrokerConfig) -> RabbitMqConfig:
    if isinstance(config, RabbitMqConfig):
        config.validate()
        return config
    allowed = {field.name for field in fields(RabbitMqConfig)}
    return RabbitMqConfig(**{key: value for key, value in config.__dict__.items() if key in allowed})


__all__ = ["RabbitMqConfig", "RabbitMqConsumer", "RabbitMqProducer", "register"]
