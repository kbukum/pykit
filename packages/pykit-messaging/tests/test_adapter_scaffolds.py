from __future__ import annotations

import importlib
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from pykit_errors import AppError
from pykit_messaging import MessageConsumer, MessageProducer, MessagingRegistry
from pykit_messaging.kafka import KafkaConfig, KafkaConsumer, KafkaProducer
from pykit_messaging.kafka import register as register_kafka
from pykit_messaging.nats import NatsConfig, NatsConsumer, NatsProducer
from pykit_messaging.nats import register as register_nats
from pykit_messaging.rabbitmq import (
    RabbitMqConfig,
    RabbitMqConsumer,
    RabbitMqProducer,
)
from pykit_messaging.rabbitmq import (
    register as register_rabbitmq,
)


def test_core_import_does_not_import_optional_broker_sdks() -> None:
    code = """
import builtins
import sys

blocked = {"aiokafka", "nats", "aio_pika"}
real_import = builtins.__import__

def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name.split(".")[0] in blocked:
        raise AssertionError(f"optional SDK imported: {name}")
    return real_import(name, globals, locals, fromlist, level)

builtins.__import__ = guarded_import
import pykit_messaging
assert "pykit_messaging.kafka" not in sys.modules
assert "pykit_messaging.nats" not in sys.modules
assert "pykit_messaging.rabbitmq" not in sys.modules
assert pykit_messaging.MessagingRegistry().producer_adapters() == []
"""
    result = subprocess.run([sys.executable, "-c", code], check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_register_kafka_is_config_free_and_creates_real_adapter_instances() -> None:
    registry = MessagingRegistry()

    register_kafka(registry)

    assert registry.producer_adapters() == ["kafka"]
    assert registry.consumer_adapters() == ["kafka"]
    producer = registry.producer(KafkaConfig(brokers=["localhost:9092"]))
    consumer = registry.consumer(KafkaConfig(topics=["events"]))
    assert isinstance(producer, KafkaProducer)
    assert isinstance(consumer, KafkaConsumer)
    assert isinstance(producer, MessageProducer)
    assert isinstance(consumer, MessageConsumer)


def test_register_nats_is_config_free_and_creates_real_adapter_instances() -> None:
    registry = MessagingRegistry()

    register_nats(registry)

    assert registry.producer_adapters() == ["nats"]
    assert registry.consumer_adapters() == ["nats"]
    producer = registry.producer(NatsConfig(url="nats://localhost:4222", allow_insecure_dev=True))
    consumer = registry.consumer(NatsConfig(topics=["events"]))
    assert isinstance(producer, NatsProducer)
    assert isinstance(consumer, NatsConsumer)
    assert isinstance(producer, MessageProducer)
    assert isinstance(consumer, MessageConsumer)


def test_nats_config_repr_redacts_connection_urls() -> None:
    cfg = NatsConfig(url="tls://broker:4222", brokers=["tls://broker:4222"], token="token-secret")
    rendered = repr(cfg)
    assert "token-secret" not in rendered
    assert "user-secret" not in rendered
    assert "url=" not in rendered
    assert "brokers=" not in rendered


@pytest.mark.asyncio
async def test_nats_producer_uses_nats_py(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = SimpleNamespace(publish=AsyncMock(), flush=AsyncMock(), close=AsyncMock())
    fake_nats = SimpleNamespace(connect=AsyncMock(return_value=fake_client))

    real_import_module = importlib.import_module

    def fake_import_module(name: str) -> object:
        if name == "nats":
            return fake_nats
        return real_import_module(name)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    producer = NatsProducer(NatsConfig(url="nats://broker:4222", brokers=[], allow_insecure_dev=True))
    await producer.send("events", b"payload", key="k1", headers={"h": "v"})
    await producer.flush()
    await producer.close()

    fake_nats.connect.assert_awaited_once_with(
        servers=["nats://broker:4222"],
        connect_timeout=2.0,
        max_reconnect_attempts=3,
        reconnect_time_wait=2.0,
        allow_reconnect=True,
    )
    fake_client.publish.assert_awaited_once_with(
        "events",
        b"payload",
        headers={"h": "v", "message-key": "k1"},
    )
    fake_client.flush.assert_awaited_once_with(timeout=30.0)
    fake_client.close.assert_awaited_once()


def test_register_rabbitmq_is_config_free_and_creates_real_adapter_instances() -> None:
    registry = MessagingRegistry()

    register_rabbitmq(registry)

    assert registry.producer_adapters() == ["rabbitmq"]
    assert registry.consumer_adapters() == ["rabbitmq"]
    producer = registry.producer(RabbitMqConfig(url="amqp://localhost:5672", allow_insecure_dev=True))
    consumer = registry.consumer(RabbitMqConfig(topics=["events"]))
    assert isinstance(producer, RabbitMqProducer)
    assert isinstance(consumer, RabbitMqConsumer)
    assert isinstance(producer, MessageProducer)
    assert isinstance(consumer, MessageConsumer)


def test_rabbitmq_config_repr_redacts_connection_url() -> None:
    cfg = RabbitMqConfig(url="amqps://broker:5671/", username="user-secret", password="password-secret")
    rendered = repr(cfg)
    assert "user-secret" not in rendered
    assert "password-secret" not in rendered
    assert "url=" not in rendered


@pytest.mark.asyncio
async def test_rabbitmq_producer_uses_aio_pika(monkeypatch: pytest.MonkeyPatch) -> None:
    published: list[tuple[object, str]] = []

    class FakeMessage:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class FakeExchange:
        async def publish(self, message: object, *, routing_key: str) -> None:
            published.append((message, routing_key))

    fake_exchange = FakeExchange()
    fake_channel = SimpleNamespace(
        default_exchange=fake_exchange,
        close=AsyncMock(),
    )
    fake_connection = SimpleNamespace(
        channel=AsyncMock(return_value=fake_channel),
        close=AsyncMock(),
    )
    fake_aio_pika = SimpleNamespace(
        Message=FakeMessage,
        DeliveryMode=SimpleNamespace(PERSISTENT="persistent"),
        ExchangeType=SimpleNamespace(DIRECT="direct"),
        connect_robust=AsyncMock(return_value=fake_connection),
    )

    real_import_module = importlib.import_module

    def fake_import_module(name: str) -> object:
        if name == "aio_pika":
            return fake_aio_pika
        return real_import_module(name)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    producer = RabbitMqProducer(RabbitMqConfig(url="amqp://broker/", allow_insecure_dev=True))
    await producer.send("events", b"payload", key="k1", headers={"h": "v"})
    await producer.close()

    fake_aio_pika.connect_robust.assert_awaited_once_with("amqp://broker/", timeout=30.0)
    fake_connection.channel.assert_awaited_once_with(publisher_confirms=True)
    assert len(published) == 1
    message, routing_key = published[0]
    assert routing_key == "events"
    assert message.kwargs == {
        "body": b"payload",
        "headers": {"h": "v"},
        "correlation_id": "k1",
        "delivery_mode": "persistent",
    }
    fake_channel.close.assert_awaited_once()
    fake_connection.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_adapter_producers_validate_topic_before_connecting() -> None:
    kafka_producer = KafkaProducer(KafkaConfig())
    with pytest.raises(AppError):
        await kafka_producer.send("bad topic", b"payload")

    nats_producer = NatsProducer(NatsConfig(url="nats://broker:4222", allow_insecure_dev=True))
    with pytest.raises(AppError):
        await nats_producer.send("bad topic", b"payload")

    rabbit_producer = RabbitMqProducer(RabbitMqConfig(url="amqp://broker/", allow_insecure_dev=True))
    with pytest.raises(AppError):
        await rabbit_producer.send("bad topic", b"payload")


def test_adapter_package_imports_do_not_import_optional_broker_sdks() -> None:
    code = """
import builtins
import sys

blocked = {"aiokafka", "nats", "aio_pika"}
real_import = builtins.__import__

def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name.split(".")[0] in blocked:
        raise AssertionError(f"optional SDK imported: {name}")
    return real_import(name, globals, locals, fromlist, level)

builtins.__import__ = guarded_import
import pykit_messaging.kafka
import pykit_messaging.nats
import pykit_messaging.rabbitmq
assert "aiokafka" not in sys.modules
assert "nats" not in sys.modules
assert "aio_pika" not in sys.modules
"""
    result = subprocess.run([sys.executable, "-c", code], check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.asyncio
async def test_missing_optional_sdk_errors_point_to_extras(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing_sdk(name: str) -> object:
        if name in {"aiokafka", "aiokafka.errors", "nats", "aio_pika"}:
            raise ImportError(name)
        return importlib.import_module(name)

    monkeypatch.setattr(importlib, "import_module", missing_sdk)

    with pytest.raises(ImportError, match=r"pykit-messaging\[kafka\]"):
        await KafkaProducer(KafkaConfig()).start()
    with pytest.raises(ImportError, match=r"pykit-messaging\[nats\]"):
        await NatsProducer(NatsConfig()).start()
    with pytest.raises(ImportError, match=r"pykit-messaging\[rabbitmq\]"):
        await RabbitMqProducer(RabbitMqConfig()).start()
