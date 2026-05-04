"""Kafka consumer built on aiokafka."""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import logging
from typing import Protocol

from pykit_messaging.kafka.config import KafkaConfig
from pykit_messaging.types import Event, EventHandler, Message, MessageHandler
from pykit_resilience import RetryConfig, RetryExhaustedError, calculate_backoff, retry

logger = logging.getLogger(__name__)


class _KafkaConsumerRecord(Protocol):
    key: bytes | None
    value: bytes
    topic: str
    partition: int
    offset: int
    headers: list[tuple[str | bytes, bytes]] | None


class _KafkaConsumerClient(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    def subscribe(self, topics: list[str]) -> object: ...

    async def commit(self) -> object: ...

    def __aiter__(self) -> object: ...


class _KafkaErrorFallback(Exception):
    pass


AIOKafkaConsumer: object | None = None
KafkaError: type[Exception] = _KafkaErrorFallback
KafkaConnectionError: type[Exception] = _KafkaErrorFallback


def _load_aiokafka() -> None:
    global AIOKafkaConsumer, KafkaConnectionError, KafkaError
    if AIOKafkaConsumer is not None:
        return
    try:
        aiokafka = importlib.import_module("aiokafka")
        aiokafka_errors = importlib.import_module("aiokafka.errors")
    except ImportError as exc:
        msg = "aiokafka is required for Kafka messaging; install pykit-messaging[kafka]"
        raise ImportError(msg) from exc
    AIOKafkaConsumer = aiokafka.AIOKafkaConsumer
    KafkaError = aiokafka_errors.KafkaError
    KafkaConnectionError = aiokafka_errors.KafkaConnectionError


_MAX_START_RETRIES = 30
_START_BACKOFF_BASE = 1.0
_START_BACKOFF_MAX = 10.0


class KafkaConsumer:
    """Async Kafka consumer with automatic reconnection."""

    def __init__(self, config: KafkaConfig) -> None:
        self._config = config
        self._consumer: _KafkaConsumerClient | None = None
        self._stopped = False

    def _build_kwargs(self) -> dict[str, object]:
        cfg = self._config
        kwargs: dict[str, object] = {
            "bootstrap_servers": ",".join(cfg.brokers),
            "group_id": cfg.consumer_group or cfg.group_id or None,
            "auto_offset_reset": cfg.auto_offset_reset,
            "session_timeout_ms": cfg.session_timeout_ms,
            "heartbeat_interval_ms": cfg.heartbeat_interval_ms,
            "security_protocol": cfg.security_protocol,
            "enable_auto_commit": cfg.commit_strategy.value == "auto",
            "request_timeout_ms": cfg.request_timeout_ms,
            "retry_backoff_ms": cfg.retry_backoff_ms,
        }
        kwargs["max_poll_records"] = cfg.max_poll_records or cfg.max_in_flight
        if cfg.ssl_context is not None:
            kwargs["ssl_context"] = cfg.ssl_context
        if cfg.sasl_mechanism:
            kwargs["sasl_mechanism"] = cfg.sasl_mechanism
            kwargs["sasl_plain_username"] = cfg.sasl_username
            kwargs["sasl_plain_password"] = cfg.sasl_password
        return kwargs

    async def start(self) -> None:
        """Create and start the underlying AIOKafkaConsumer with retry."""
        _load_aiokafka()
        self._stopped = False
        cfg = self._config
        kwargs = self._build_kwargs()
        topics = cfg.subscriptions or cfg.topics
        topics_str = ", ".join(topics) if topics else "(none)"

        def _on_retry(attempt: int, _exc: Exception, _backoff: float) -> None:
            if attempt == 1:
                logger.warning(
                    "Kafka not ready, retrying connection (topics: %s)...",
                    topics_str,
                )

        async def _start_once() -> None:
            try:
                consumer_factory = AIOKafkaConsumer
                if consumer_factory is None:
                    raise RuntimeError("aiokafka consumer factory was not loaded")
                self._consumer = consumer_factory(*topics, **kwargs)
                await self._consumer.start()
            except KafkaError:
                if self._consumer is not None:
                    with contextlib.suppress(KafkaError, RuntimeError):
                        await self._consumer.stop()
                    self._consumer = None
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
                "Kafka consumer failed to start after %d attempts (topics: %s)",
                _MAX_START_RETRIES,
                topics_str,
            )
            raise exc.last_error from exc

    async def _reconnect(self) -> None:
        """Stop current consumer and restart with backoff."""
        topics = self._config.subscriptions or self._config.topics
        topics_str = ", ".join(topics) if topics else "(none)"
        # Silently close old consumer
        if self._consumer is not None:
            with contextlib.suppress(KafkaError, RuntimeError):
                await self._consumer.stop()
            self._consumer = None

        attempt = 1
        backoff_config = RetryConfig(
            initial_backoff=1.0,
            max_backoff=_START_BACKOFF_MAX,
            jitter=0.0,
        )
        backoff = calculate_backoff(attempt, backoff_config)
        while not self._stopped:
            try:
                consumer_factory = AIOKafkaConsumer
                if consumer_factory is None:
                    raise RuntimeError("aiokafka consumer factory was not loaded")
                self._consumer = consumer_factory(*topics, **self._build_kwargs())
                await self._consumer.start()
                logger.info("Kafka consumer reconnected (topics: %s)", topics_str)
                return
            except KafkaError:
                if self._stopped:
                    return
                logger.warning(
                    "Kafka reconnect failed, retrying in %.0fs (topics: %s)...",
                    backoff,
                    topics_str,
                )
                await asyncio.sleep(backoff)
                attempt += 1
                backoff = calculate_backoff(attempt, backoff_config)

    async def stop(self) -> None:
        """Stop the consumer."""
        self._stopped = True
        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None

    async def subscribe(self, topics: list[str]) -> None:
        """Update topic subscription."""
        if self._consumer is None:
            raise RuntimeError("Consumer is not started")
        self._consumer.subscribe(topics)

    async def consume(self, handler: MessageHandler) -> None:
        """Read messages and dispatch to *handler*, reconnecting on broker loss."""
        while not self._stopped:
            if self._consumer is None:
                raise RuntimeError("Consumer is not started")

            try:
                async for record in self._consumer:
                    if self._stopped:
                        return
                    headers: dict[str, str] = {}
                    if record.headers:
                        headers = {
                            (k.decode() if isinstance(k, bytes) else k): v.decode() for k, v in record.headers
                        }

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

                    if self._config.commit_strategy.value == "post_handler_success":
                        with contextlib.suppress(KafkaError):
                            await self._consumer.commit()

            except (KafkaConnectionError, KafkaError) as e:
                if self._stopped:
                    return
                logger.warning("Kafka connection lost (%s), reconnecting...", e)
                await self._reconnect()

    async def consume_events(self, handler: EventHandler) -> None:
        """Deserialize messages as events and dispatch to *handler*."""

        async def _wrapper(msg: Message) -> None:
            event = Event.from_json(msg.value)
            await handler(event)

        await self.consume(_wrapper)

    async def close(self) -> None:
        """Close the consumer (alias for stop)."""
        await self.stop()
