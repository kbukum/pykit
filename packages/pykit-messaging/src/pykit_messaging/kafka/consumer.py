"""Kafka consumer built on aiokafka."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiokafka import AIOKafkaConsumer  # type: ignore[import-untyped]

from pykit_messaging.kafka.config import KafkaConfig
from pykit_messaging.types import Event, EventHandler, Message, MessageHandler

logger = logging.getLogger(__name__)

_MAX_START_RETRIES = 30
_START_BACKOFF_BASE = 1.0
_START_BACKOFF_MAX = 10.0


class KafkaConsumer:
    """Async Kafka consumer."""

    def __init__(self, config: KafkaConfig) -> None:
        self._config = config
        self._consumer: AIOKafkaConsumer | None = None

    async def start(self) -> None:
        """Create and start the underlying AIOKafkaConsumer with retry."""
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

        topics_str = ", ".join(cfg.topics) if cfg.topics else "(none)"
        for attempt in range(1, _MAX_START_RETRIES + 1):
            try:
                self._consumer = AIOKafkaConsumer(*cfg.topics, **kwargs)
                await self._consumer.start()
                return
            except Exception:
                if attempt == _MAX_START_RETRIES:
                    logger.error(
                        "Kafka consumer failed to start after %d attempts (topics: %s)",
                        _MAX_START_RETRIES,
                        topics_str,
                    )
                    raise
                backoff = min(_START_BACKOFF_BASE * (2 ** (attempt - 1)), _START_BACKOFF_MAX)
                if attempt == 1:
                    logger.warning(
                        "Kafka not ready, retrying connection (topics: %s)...",
                        topics_str,
                    )
                await asyncio.sleep(backoff)

    async def stop(self) -> None:
        """Stop the consumer."""
        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None

    async def subscribe(self, topics: list[str]) -> None:
        """Update topic subscription."""
        if self._consumer is None:
            raise RuntimeError("Consumer is not started")
        self._consumer.subscribe(topics)

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

    async def close(self) -> None:
        """Close the consumer (alias for stop)."""
        await self.stop()
