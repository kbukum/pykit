"""RabbitMQ consumer adapter."""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import Awaitable, Mapping
from datetime import UTC, datetime
from types import TracebackType
from typing import Protocol, cast

from pykit_messaging.rabbitmq.config import RabbitMqConfig
from pykit_messaging.types import Message, MessageHandler


class _RabbitRawMessage(Protocol):
    body: bytes
    routing_key: str
    correlation_id: str | None
    headers: object | None

    def process(self) -> _RabbitMessageProcess: ...


class _RabbitMessageProcess(Protocol):
    async def __aenter__(self) -> object: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> object: ...


class _Exchange(Protocol):
    async def publish(self, message: object, *, routing_key: str) -> object: ...


class _Queue(Protocol):
    async def bind(self, exchange: _Exchange, *, routing_key: str) -> object: ...

    async def consume(self, callback: object, *, no_ack: bool = False) -> str: ...

    async def cancel(self, consumer_tag: str) -> object: ...


class _Channel(Protocol):
    default_exchange: _Exchange

    async def set_qos(self, *, prefetch_count: int) -> object: ...

    async def declare_exchange(self, name: str, exchange_type: object, *, durable: bool) -> _Exchange: ...

    async def declare_queue(
        self,
        name: str,
        *,
        durable: bool,
        auto_delete: bool = False,
        exclusive: bool = False,
    ) -> _Queue: ...

    async def close(self) -> object: ...


class _Connection(Protocol):
    async def channel(self, *, publisher_confirms: bool = True) -> _Channel: ...

    async def close(self) -> object: ...


class _AioPikaModule(Protocol):
    ExchangeType: object

    def connect_robust(self, url: str, **kwargs: object) -> Awaitable[_Connection]: ...


class RabbitMqConsumer:
    """RabbitMQ-backed consumer requiring the ``rabbitmq`` extra."""

    def __init__(self, config: RabbitMqConfig) -> None:
        config.validate()
        self._config = config
        self._topics = list(config.topics)
        self._aio_pika: _AioPikaModule | None = None
        self._connection: _Connection | None = None
        self._channel: _Channel | None = None
        self._exchange: _Exchange | None = None
        self._consumer_tags: list[tuple[_Queue, str]] = []
        self._closed = asyncio.Event()

    async def start(self) -> None:
        """Connect to RabbitMQ and open a consuming channel."""
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
        self._channel = await self._connection.channel(publisher_confirms=False)
        await self._channel.set_qos(prefetch_count=self._config.max_in_flight)
        self._exchange = await _resolve_exchange(aio_pika, self._channel, self._config)
        self._closed.clear()

    async def subscribe(self, topics: list[str]) -> None:
        """Set queue names/routing keys consumed by this consumer."""
        self._topics = list(topics)

    async def consume(self, handler: MessageHandler) -> None:
        """Consume configured queues until closed."""
        await self.start()
        channel = _require_channel(self._channel)
        exchange = _require_exchange(self._exchange)

        async def _callback(raw_message: object) -> None:
            message = cast("_RabbitRawMessage", raw_message)
            if self._config.auto_ack:
                await handler(_to_message(message))
                return
            async with message.process():
                await handler(_to_message(message))

        for topic in self._topics:
            queue = await channel.declare_queue(
                self._config.queue_for(topic),
                durable=self._config.durable,
                auto_delete=self._config.auto_delete,
                exclusive=self._config.exclusive,
            )
            if self._config.exchange_name:
                await queue.bind(exchange, routing_key=self._config.routing_key(topic))
            self._consumer_tags.append((queue, await queue.consume(_callback, no_ack=self._config.auto_ack)))
        await self._closed.wait()

    async def close(self) -> None:
        """Cancel consumers and close the RabbitMQ connection."""
        self._closed.set()
        for queue, consumer_tag in self._consumer_tags:
            await queue.cancel(consumer_tag)
        self._consumer_tags.clear()
        if self._channel is not None:
            await self._channel.close()
            self._channel = None
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
        self._exchange = None


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


def _require_channel(channel: _Channel | None) -> _Channel:
    if channel is None:
        raise RuntimeError("RabbitMQ channel is not started")
    return channel


def _require_exchange(exchange: _Exchange | None) -> _Exchange:
    if exchange is None:
        raise RuntimeError("RabbitMQ exchange is not started")
    return exchange


def _to_message(raw_message: _RabbitRawMessage) -> Message:
    headers = _headers_to_dict(raw_message.headers)
    return Message(
        key=raw_message.correlation_id,
        value=raw_message.body,
        topic=raw_message.routing_key,
        partition=0,
        offset=0,
        timestamp=datetime.now(UTC),
        headers=headers,
    )


def _headers_to_dict(raw_headers: object | None) -> dict[str, str]:
    if raw_headers is None or not isinstance(raw_headers, Mapping):
        return {}
    headers_map = cast("Mapping[object, object]", raw_headers)
    return {str(key): str(value) for key, value in headers_map.items()}
