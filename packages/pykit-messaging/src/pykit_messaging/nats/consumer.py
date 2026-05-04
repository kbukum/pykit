"""NATS consumer adapter."""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import Awaitable, Mapping
from datetime import UTC, datetime
from inspect import isawaitable
from typing import Protocol, cast

from pykit_messaging.nats.config import NatsConfig
from pykit_messaging.types import Message, MessageHandler


class _NatsRawMessage(Protocol):
    subject: str
    data: bytes
    headers: object | None


class _NatsClient(Protocol):
    def close(self) -> Awaitable[None] | None: ...

    async def subscribe(self, subject: str, *, cb: object, queue: str = "") -> object: ...


class _NatsModule(Protocol):
    def connect(self, **kwargs: object) -> Awaitable[_NatsClient]: ...


class NatsConsumer:
    """NATS-backed message consumer requiring the ``nats`` extra."""

    def __init__(self, config: NatsConfig) -> None:
        config.validate()
        self._config = config
        self._topics = list(config.topics or config.subscriptions)
        self._client: _NatsClient | None = None
        self._subscriptions: list[object] = []
        self._closed = asyncio.Event()

    async def start(self) -> None:
        """Connect to NATS."""
        if self._client is not None:
            return
        nats = _import_nats()
        kwargs: dict[str, object] = {
            "servers": self._config.servers(),
            "connect_timeout": self._config.connect_timeout,
            "max_reconnect_attempts": self._config.retries,
            "reconnect_time_wait": self._config.reconnect_time_wait,
            "allow_reconnect": self._config.allow_reconnect,
        }
        if self._config.token:
            kwargs["token"] = self._config.token
        if self._config.username:
            kwargs["user"] = self._config.username
            kwargs["password"] = self._config.password
        self._client = await nats.connect(**kwargs)
        self._closed.clear()

    async def subscribe(self, topics: list[str]) -> None:
        """Set NATS subjects consumed by this consumer."""
        self._topics = list(topics)

    async def consume(self, handler: MessageHandler) -> None:
        """Subscribe to configured subjects and dispatch messages until closed."""
        await self.start()
        client = _require_client(self._client)

        for topic in self._topics:

            async def _make_callback(
                logical_topic: str,
            ) -> object:
                async def _callback(raw_message: object) -> None:
                    await handler(_to_message(raw_message, logical_topic))

                return _callback

            self._subscriptions.append(
                await client.subscribe(
                    self._config.subject(topic),
                    cb=await _make_callback(topic),
                    queue=self._config.queue_group,
                )
            )
        await self._closed.wait()

    async def close(self) -> None:
        """Stop consuming and close the NATS connection."""
        self._closed.set()
        for subscription in self._subscriptions:
            unsubscribe = getattr(subscription, "unsubscribe", None)
            if unsubscribe is not None:
                result = unsubscribe()
                if isawaitable(result):
                    await result
        self._subscriptions.clear()
        if self._client is None:
            return
        result = self._client.close()
        if isawaitable(result):
            await result
        self._client = None


def _import_nats() -> _NatsModule:
    try:
        return cast("_NatsModule", importlib.import_module("nats"))
    except ImportError as exc:
        msg = "nats-py is required for NATS messaging; install pykit-messaging[nats]"
        raise ImportError(msg) from exc


def _require_client(client: _NatsClient | None) -> _NatsClient:
    if client is None:
        raise RuntimeError("NATS client is not started")
    return client


def _to_message(raw_message: object, topic: str = "") -> Message:
    message = cast("_NatsRawMessage", raw_message)
    headers = _headers_to_dict(message.headers)
    key = headers.pop("message-key", None)
    # Use logical topic name if provided (when consuming via subject_prefix).
    # Fall back to broker subject if topic not specified (e.g., direct subject subscriptions).
    msg_topic = topic if topic else message.subject
    return Message(
        key=key,
        value=message.data,
        topic=msg_topic,
        partition=0,
        offset=0,
        timestamp=datetime.now(UTC),
        headers=headers,
    )


def _headers_to_dict(raw_headers: object) -> dict[str, str]:
    if raw_headers is None:
        return {}
    if not isinstance(raw_headers, Mapping):
        return {}
    headers_map = cast("Mapping[object, object]", raw_headers)
    headers: dict[str, str] = {}
    for key, value in headers_map.items():
        if isinstance(value, list):
            headers[str(key)] = str(value[-1]) if value else ""
        else:
            headers[str(key)] = str(value)
    return headers
