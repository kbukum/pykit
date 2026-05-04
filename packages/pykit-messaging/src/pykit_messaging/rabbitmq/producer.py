"""RabbitMQ producer adapter."""

from __future__ import annotations

import importlib
from collections.abc import Awaitable, Callable
from typing import Protocol, cast

from pykit_messaging.rabbitmq.config import RabbitMqConfig
from pykit_messaging.types import Event, JsonValue, Message
from pykit_util import JsonCodec


class _Exchange(Protocol):
    async def publish(self, message: object, *, routing_key: str) -> object: ...


class _Channel(Protocol):
    default_exchange: _Exchange

    async def declare_exchange(self, name: str, exchange_type: object, *, durable: bool) -> _Exchange: ...

    async def close(self) -> object: ...


class _Connection(Protocol):
    async def channel(self, *, publisher_confirms: bool = True) -> _Channel: ...

    async def close(self) -> object: ...


class _DeliveryMode(Protocol):
    PERSISTENT: object


class _AioPikaModule(Protocol):
    Message: Callable[..., object]
    DeliveryMode: _DeliveryMode
    ExchangeType: object

    def connect_robust(self, url: str, **kwargs: object) -> Awaitable[_Connection]: ...


class RabbitMqProducer:
    """RabbitMQ-backed producer requiring the ``rabbitmq`` extra."""

    def __init__(self, config: RabbitMqConfig) -> None:
        config.validate()
        self._config = config
        self._aio_pika: _AioPikaModule | None = None
        self._connection: _Connection | None = None
        self._channel: _Channel | None = None
        self._exchange: _Exchange | None = None

    async def start(self) -> None:
        """Connect to RabbitMQ and open a channel."""
        if self._connection is not None:
            return
        aio_pika = _import_aio_pika()
        self._aio_pika = aio_pika
        connect_kwargs: dict[str, object] = {"timeout": self._config.request_timeout_ms / 1000}
        if self._config.username:
            connect_kwargs["login"] = self._config.username
            connect_kwargs["password"] = self._config.password
        if self._config.connection_name:
            connect_kwargs["client_properties"] = {"connection_name": self._config.connection_name}
        self._connection = await aio_pika.connect_robust(self._config.url, **connect_kwargs)
        self._channel = await self._connection.channel(publisher_confirms=self._config.publisher_confirms)
        self._exchange = await _resolve_exchange(aio_pika, self._channel, self._config)

    async def send(
        self,
        topic: str,
        value: bytes,
        key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Publish bytes using *topic* as the routing key."""
        routing_key = self._publish_routing_key(topic)
        await self.start()
        aio_pika = _require_module(self._aio_pika)
        exchange = _require_exchange(self._exchange)
        message = aio_pika.Message(
            body=value,
            headers=dict(headers or {}),
            correlation_id=key,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await exchange.publish(message, routing_key=routing_key)

    async def send_event(self, topic: str, event: Event) -> None:
        """Serialize and publish an event."""
        await self.send(topic, event.to_json(), key=event.id, headers={"event-type": event.type})

    async def send_json(self, topic: str, data: JsonValue, key: str | None = None) -> None:
        """Serialize and publish JSON."""
        await self.send(topic, JsonCodec[JsonValue](stringify_unknown=False).encode(data), key=key)

    async def send_batch(self, messages: list[Message]) -> None:
        """Publish messages sequentially."""
        for message in messages:
            await self.send(message.topic, message.value, key=message.key, headers=message.headers)

    async def flush(self) -> None:
        """No-op; publisher confirms await broker acceptance per publish."""

    async def close(self) -> None:
        """Close the RabbitMQ channel and connection."""
        if self._channel is not None:
            await self._channel.close()
            self._channel = None
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
        self._exchange = None

    def _publish_routing_key(self, topic: str) -> str:
        if not self._config.exchange_name:
            return self._config.queue_for(topic)
        return self._config.routing_key(topic)


def _import_aio_pika() -> _AioPikaModule:
    try:
        return cast("_AioPikaModule", importlib.import_module("aio_pika"))
    except ImportError as exc:
        msg = "aio-pika is required for RabbitMQ messaging; install pykit-messaging[rabbitmq]"
        raise ImportError(msg) from exc


async def _resolve_exchange(aio_pika: _AioPikaModule, channel: _Channel, config: RabbitMqConfig) -> _Exchange:
    if not config.exchange_name:
        return channel.default_exchange
    exchange_type = getattr(aio_pika.ExchangeType, config.exchange_type.upper())
    return await channel.declare_exchange(config.exchange_name, exchange_type, durable=config.durable)


def _require_module(module: _AioPikaModule | None) -> _AioPikaModule:
    if module is None:
        raise RuntimeError("aio-pika is not loaded")
    return module


def _require_exchange(exchange: _Exchange | None) -> _Exchange:
    if exchange is None:
        raise RuntimeError("RabbitMQ exchange is not started")
    return exchange
