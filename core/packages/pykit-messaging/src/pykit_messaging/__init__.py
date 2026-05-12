"""pykit-messaging — Transport-agnostic messaging abstractions with pluggable providers."""

from __future__ import annotations

from pykit_messaging.batch import BatchConfig, BatchProducer
from pykit_messaging.config import BrokerConfig, CommitStrategy, DeliveryGuarantee, DLQPolicy
from pykit_messaging.errors import ErrorClassifier
from pykit_messaging.event_publisher import EventPublisher
from pykit_messaging.handler import FuncHandler, HandlerMiddleware, MessageHandlerProtocol, chain_handlers
from pykit_messaging.managed_consumer import ManagedConsumer
from pykit_messaging.managed_producer import ManagedProducer
from pykit_messaging.memory import (
    InMemoryBroker,
    InMemoryConsumer,
    InMemoryProducer,
    MemoryConfig,
    clear_memory_brokers,
)
from pykit_messaging.metrics import MetricsCollector, NoopMetrics
from pykit_messaging.middleware import (
    CircuitBreakerConfig,
    CircuitBreakerHandler,
    DeadLetterConfig,
    DeadLetterProducer,
    DedupConfig,
    DedupHandler,
    MetricsHandler,
    RetryConfig,
    RetryHandler,
    StackBuilder,
    circuit_breaker,
    dedup,
    instrument,
    retry,
)
from pykit_messaging.protocols import ControllableConsumer, MessageConsumer, MessageProducer
from pykit_messaging.registry import MessagingRegistry
from pykit_messaging.router import MessageRouter
from pykit_messaging.runner import ConsumerRunner
from pykit_messaging.testing import assert_no_messages, assert_published, assert_published_n, wait_for_message
from pykit_messaging.translator import JsonTranslator, MessageTranslator
from pykit_messaging.types import Event, EventHandler, JsonValue, Message, MessageHandler

__all__ = [
    "BatchConfig",
    "BatchProducer",
    "BrokerConfig",
    "CircuitBreakerConfig",
    "CircuitBreakerHandler",
    "ConsumerRunner",
    "ControllableConsumer",
    "CommitStrategy",
    "DeadLetterConfig",
    "DeadLetterProducer",
    "DeliveryGuarantee",
    "DLQPolicy",
    "DedupConfig",
    "DedupHandler",
    "ErrorClassifier",
    "Event",
    "EventHandler",
    "EventPublisher",
    "FuncHandler",
    "HandlerMiddleware",
    "InMemoryBroker",
    "InMemoryConsumer",
    "InMemoryProducer",
    "JsonTranslator",
    "JsonValue",
    "ManagedConsumer",
    "ManagedProducer",
    "MemoryConfig",
    "Message",
    "MessageConsumer",
    "MessageHandler",
    "MessageHandlerProtocol",
    "MessageProducer",
    "MessageRouter",
    "MessageTranslator",
    "MessagingRegistry",
    "MetricsCollector",
    "MetricsHandler",
    "NoopMetrics",
    "RetryConfig",
    "RetryHandler",
    "StackBuilder",
    "assert_no_messages",
    "assert_published",
    "assert_published_n",
    "chain_handlers",
    "circuit_breaker",
    "clear_memory_brokers",
    "dedup",
    "instrument",
    "retry",
    "wait_for_message",
]
