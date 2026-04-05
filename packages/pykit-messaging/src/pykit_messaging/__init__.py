"""pykit-messaging — Transport-agnostic messaging abstractions with pluggable providers."""

from __future__ import annotations

from pykit_messaging.config import BrokerConfig
from pykit_messaging.errors import ErrorClassifier
from pykit_messaging.protocols import MessageConsumer, MessageProducer
from pykit_messaging.types import Event, EventHandler, Message, MessageHandler

__all__ = [
    "BrokerConfig",
    "ErrorClassifier",
    "Event",
    "EventHandler",
    "Message",
    "MessageConsumer",
    "MessageHandler",
    "MessageProducer",
]
