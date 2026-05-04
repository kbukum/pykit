"""NATS provider for pykit-messaging."""

from __future__ import annotations

from dataclasses import fields
from typing import TYPE_CHECKING

from pykit_messaging.config import BrokerConfig
from pykit_messaging.nats.config import ADAPTER_NAME, NatsConfig
from pykit_messaging.nats.consumer import NatsConsumer
from pykit_messaging.nats.producer import NatsProducer

if TYPE_CHECKING:
    from pykit_messaging.registry import MessagingRegistry


def register(registry: MessagingRegistry) -> None:
    """Register config-free NATS producer and consumer factories."""
    registry.register_producer(ADAPTER_NAME, lambda config: NatsProducer(_config_from(config)))
    registry.register_consumer(ADAPTER_NAME, lambda config: NatsConsumer(_config_from(config)))


def _config_from(config: BrokerConfig) -> NatsConfig:
    if isinstance(config, NatsConfig):
        config.validate()
        return config
    allowed = {field.name for field in fields(NatsConfig)}
    return NatsConfig(**{key: value for key, value in config.__dict__.items() if key in allowed})


__all__ = ["NatsConfig", "NatsConsumer", "NatsProducer", "register"]
