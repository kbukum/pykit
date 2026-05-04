"""NATS producer adapter."""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import Awaitable
from inspect import isawaitable
from typing import Protocol, cast

from pykit_messaging.nats.config import NatsConfig
from pykit_messaging.types import Event, JsonValue, Message
from pykit_util import JsonCodec


class _NatsClient(Protocol):
    async def publish(
        self,
        subject: str,
        payload: bytes = b"",
        *,
        headers: dict[str, str] | None = None,
    ) -> None: ...

    async def flush(self, timeout: float | None = None) -> None: ...

    def close(self) -> Awaitable[None] | None: ...

    async def drain(self) -> object: ...


class _NatsModule(Protocol):
    def connect(self, **kwargs: object) -> Awaitable[_NatsClient]: ...


class NatsProducer:
    """NATS-backed message producer requiring the ``nats`` extra."""

    def __init__(self, config: NatsConfig) -> None:
        config.validate()
        self._config = config
        self._client: _NatsClient | None = None

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

    async def send(
        self,
        topic: str,
        value: bytes,
        key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Publish bytes to a NATS subject."""
        subject = self._config.subject(topic)
        await self.start()
        outgoing_headers = dict(headers or {})
        if key is not None:
            outgoing_headers["message-key"] = key
        await _require_client(self._client).publish(subject, value, headers=outgoing_headers or None)

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
        """Flush pending publishes."""
        if self._client is not None:
            await self._client.flush(timeout=self._config.request_timeout_ms / 1000)

    async def close(self) -> None:
        """Close the NATS connection."""
        if self._client is None:
            return
        drain = getattr(self._client, "drain", None)
        if self._config.drain_timeout > 0 and drain is not None:
            try:
                await asyncio.wait_for(drain(), timeout=self._config.drain_timeout)
            except TimeoutError:
                await _close_client(self._client)
        else:
            await _close_client(self._client)
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


async def _close_client(client: _NatsClient) -> None:
    result = client.close()
    if isawaitable(result):
        await result
