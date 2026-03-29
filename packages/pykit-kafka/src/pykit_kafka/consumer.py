"""Kafka consumer built on aiokafka."""

from __future__ import annotations

from typing import Any

from aiokafka import AIOKafkaConsumer

from pykit_kafka.config import KafkaConfig
from pykit_kafka.types import Event, EventHandler, Message, MessageHandler


class KafkaConsumer:
    """Async Kafka consumer."""

    def __init__(self, config: KafkaConfig) -> None:
        self._config = config
        self._consumer: AIOKafkaConsumer | None = None

    async def start(self) -> None:
        """Create and start the underlying AIOKafkaConsumer."""
        cfg = self._config
        kwargs: dict[str, Any] = {
            "bootstrap_servers": ",".join(cfg.brokers),
            "group_id": cfg.group_id or None,
            "auto_offset_reset": cfg.auto_offset_reset,
            "session_timeout_ms": cfg.session_timeout_ms,
            "heartbeat_interval_ms": cfg.heartbeat_interval_ms,
            "security_protocol": cfg.security_protocol,
        }
        if cfg.sasl_mechanism:
            kwargs["sasl_mechanism"] = cfg.sasl_mechanism
            kwargs["sasl_plain_username"] = cfg.sasl_username
            kwargs["sasl_plain_password"] = cfg.sasl_password

        self._consumer = AIOKafkaConsumer(*cfg.topics, **kwargs)
        await self._consumer.start()

    async def stop(self) -> None:
        """Stop the consumer."""
        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None

    async def consume(self, handler: MessageHandler) -> None:
        """Read messages and dispatch to *handler* until stopped."""
        if self._consumer is None:
            raise RuntimeError("Consumer is not started")

        async for record in self._consumer:
            headers: dict[str, str] = {}
            if record.headers:
                headers = {(k.decode() if isinstance(k, bytes) else k): v.decode() for k, v in record.headers}

            msg = Message(
                key=record.key.decode() if record.key else None,
                value=record.value,
                topic=record.topic,
                partition=record.partition,
                offset=record.offset,
                timestamp=None,
                headers=headers,
            )
            await handler(msg)

    async def consume_events(self, handler: EventHandler) -> None:
        """Deserialize messages as events and dispatch to *handler*."""

        async def _wrapper(msg: Message) -> None:
            event = Event.from_json(msg.value)
            await handler(event)

        await self.consume(_wrapper)
