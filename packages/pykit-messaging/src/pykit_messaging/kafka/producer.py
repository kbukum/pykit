"""Kafka producer built on aiokafka."""

from __future__ import annotations

import contextlib
import importlib
import logging
from collections.abc import Callable
from typing import Protocol, cast

from pykit_messaging.config import validate_topic_name
from pykit_messaging.kafka.config import KafkaConfig
from pykit_messaging.types import Event, JsonValue, Message
from pykit_resilience import RetryConfig, RetryExhaustedError, retry
from pykit_util import JsonCodec

logger = logging.getLogger(__name__)


class _KafkaProducerClient(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def send_and_wait(
        self,
        topic: str,
        *,
        value: bytes,
        key: bytes | None = None,
        headers: list[tuple[str, bytes]] | None = None,
    ) -> object: ...

    async def flush(self) -> None: ...


class _KafkaErrorFallback(Exception):
    pass


_KafkaProducerFactory = Callable[..., _KafkaProducerClient]


AIOKafkaProducer: _KafkaProducerFactory | None = None
KafkaError: type[Exception] = _KafkaErrorFallback


def _load_aiokafka() -> None:
    global AIOKafkaProducer, KafkaError
    if AIOKafkaProducer is not None:
        return
    try:
        aiokafka = importlib.import_module("aiokafka")
        aiokafka_errors = importlib.import_module("aiokafka.errors")
    except ImportError as exc:
        msg = "aiokafka is required for Kafka messaging; install pykit-messaging[kafka]"
        raise ImportError(msg) from exc
    AIOKafkaProducer = cast("_KafkaProducerFactory", aiokafka.AIOKafkaProducer)
    KafkaError = cast("type[Exception]", aiokafka_errors.KafkaError)


_MAX_START_RETRIES = 30
_START_BACKOFF_BASE = 1.0
_START_BACKOFF_MAX = 10.0


class KafkaProducer:
    """Async Kafka producer."""

    def __init__(self, config: KafkaConfig) -> None:
        self._config = config
        self._producer: _KafkaProducerClient | None = None

    async def start(self) -> None:
        """Create and start the underlying AIOKafkaProducer with retry."""
        _load_aiokafka()
        cfg = self._config
        kwargs: dict[str, object] = {
            "bootstrap_servers": ",".join(cfg.brokers),
            "compression_type": cfg.compression_type,
            "max_batch_size": cfg.max_batch_size,
            "request_timeout_ms": cfg.request_timeout_ms,
            "retry_backoff_ms": cfg.retry_backoff_ms,
            "security_protocol": cfg.security_protocol,
            "linger_ms": cfg.linger_ms,
            "acks": cfg.acks,
            "enable_idempotence": cfg.enable_idempotence,
            "max_in_flight_requests_per_connection": cfg.max_in_flight,
        }
        if cfg.transactional_id:
            kwargs["transactional_id"] = cfg.transactional_id
        if cfg.ssl_context is not None:
            kwargs["ssl_context"] = cfg.ssl_context
        if cfg.sasl_mechanism:
            kwargs["sasl_mechanism"] = cfg.sasl_mechanism
            kwargs["sasl_plain_username"] = cfg.sasl_username
            kwargs["sasl_plain_password"] = cfg.sasl_password

        def _on_retry(attempt: int, _exc: Exception, _backoff: float) -> None:
            if attempt == 1:
                logger.warning("Kafka not ready, retrying producer connection...")

        async def _start_once() -> None:
            try:
                producer_factory = AIOKafkaProducer
                if producer_factory is None:
                    raise RuntimeError("aiokafka producer factory was not loaded")
                self._producer = producer_factory(**kwargs)
                await self._producer.start()
            except KafkaError:
                if self._producer is not None:
                    with contextlib.suppress(KafkaError, RuntimeError):
                        await self._producer.stop()
                    self._producer = None
                raise

        try:
            await retry(
                _start_once,
                RetryConfig(
                    max_attempts=_MAX_START_RETRIES,
                    initial_backoff=_START_BACKOFF_BASE,
                    max_backoff=_START_BACKOFF_MAX,
                    jitter=0.0,
                    retry_if=lambda exc: isinstance(exc, KafkaError),
                    on_retry=_on_retry,
                ),
            )
        except RetryExhaustedError as exc:
            logger.error(
                "Kafka producer failed to start after %d attempts",
                _MAX_START_RETRIES,
            )
            raise exc.last_error from exc

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
        validate_topic_name(topic, "topic")
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

    async def send_json(self, topic: str, data: JsonValue, key: str | None = None) -> None:
        """Serialize *data* as JSON and send it."""
        value = JsonCodec[JsonValue](stringify_unknown=False).encode(data)
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
