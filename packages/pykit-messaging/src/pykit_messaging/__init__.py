"""pykit-messaging — Transport-agnostic messaging abstractions with pluggable providers."""

from __future__ import annotations

from pykit_messaging.batch import BatchConfig, BatchProducer
from pykit_messaging.config import BrokerConfig
from pykit_messaging.errors import ErrorClassifier
from pykit_messaging.event_publisher import EventPublisher
from pykit_messaging.handler import FuncHandler, HandlerMiddleware, MessageHandlerProtocol, chain_handlers
from pykit_messaging.managed_consumer import ManagedConsumer
from pykit_messaging.managed_producer import ManagedProducer
from pykit_messaging.metrics import MetricsCollector, NoopMetrics
from pykit_messaging.middleware import (
    CircuitBreakerConfig,
    CircuitBreakerHandler,
    DedupConfig,
    DedupHandler,
    circuit_breaker,
    dedup,
)
from pykit_messaging.protocols import MessageConsumer, MessageProducer
from pykit_messaging.router import MessageRouter
from pykit_messaging.runner import ConsumerRunner
from pykit_messaging.testing import assert_no_messages, assert_published, assert_published_n, wait_for_message
from pykit_messaging.translator import JsonTranslator, MessageTranslator
from pykit_messaging.types import Event, EventHandler, Message, MessageHandler

__all__ = [
    "BatchConfig",
    "BatchProducer",
    "BrokerConfig",
    "CircuitBreakerConfig",
    "CircuitBreakerHandler",
    "ConsumerRunner",
    "DedupConfig",
    "DedupHandler",
    "ErrorClassifier",
    "Event",
    "EventHandler",
    "EventPublisher",
    "FuncHandler",
    "HandlerMiddleware",
    "JsonTranslator",
    "ManagedConsumer",
    "ManagedProducer",
    "Message",
    "MessageConsumer",
    "MessageHandler",
    "MessageHandlerProtocol",
    "MessageProducer",
    "MessageRouter",
    "MessageTranslator",
    "MetricsCollector",
    "NoopMetrics",
    "assert_no_messages",
    "assert_published",
    "assert_published_n",
    "chain_handlers",
    "circuit_breaker",
    "dedup",
    "wait_for_message",
]
