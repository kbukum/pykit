"""Kafka producer built on aiokafka."""

from __future__ import annotations

import json
from typing import Any

from aiokafka import AIOKafkaProducer

from pykit_messaging.kafka.config import KafkaConfig
from pykit_messaging.types import Event, Message


class KafkaProducer:
    """Async Kafka producer."""

    def __init__(self, config: KafkaConfig) -> None:
        self._config = config
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        """Create and start the underlying AIOKafkaProducer."""
        cfg = self._config
        kwargs: dict[str, Any] = {
            "bootstrap_servers": ",".join(cfg.brokers),
            "compression_type": cfg.compression_type,
            "max_batch_size": cfg.max_batch_size,
            "request_timeout_ms": cfg.request_timeout_ms,
            "retry_backoff_ms": cfg.retry_backoff_ms,
            "security_protocol": cfg.security_protocol,
        }
        if cfg.sasl_mechanism:
            kwargs["sasl_mechanism"] = cfg.sasl_mechanism
            kwargs["sasl_plain_username"] = cfg.sasl_username
            kwargs["sasl_plain_password"] = cfg.sasl_password

        self._producer = AIOKafkaProducer(**kwargs)
        await self._producer.start()

    async def stop(self) -> None:
        """Stop the producer."""
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None

    async def send(
        self,
        topic: str,
        value: bytes,
        key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Send a raw message to the given topic."""
        if self._producer is None:
            raise RuntimeError("Producer is not started")

        kafka_headers: list[tuple[str, bytes]] | None = None
        if headers:
            kafka_headers = [(k, v.encode()) for k, v in headers.items()]

        await self._producer.send_and_wait(
            topic,
            value=value,
            key=key.encode() if key else None,
            headers=kafka_headers,
        )

    async def send_event(self, topic: str, event: Event) -> None:
        """Serialize an event and send it."""
        await self.send(
            topic,
            value=event.to_json(),
            key=event.id,
            headers={"event-type": event.type},
        )

    async def send_json(self, topic: str, data: Any, key: str | None = None) -> None:
        """Serialize *data* as JSON and send it."""
        value = json.dumps(data).encode()
        await self.send(topic, value=value, key=key)

    async def send_batch(self, messages: list[Message]) -> None:
        """Send a batch of messages sequentially."""
        for msg in messages:
            await self.send(
                msg.topic,
                value=msg.value,
                key=msg.key,
                headers=dict(msg.headers) if msg.headers else None,
            )

    async def flush(self) -> None:
        """Flush pending messages."""
        if self._producer is not None:
            await self._producer.flush()

    async def close(self) -> None:
        """Close the producer (alias for stop)."""
        await self.stop()
