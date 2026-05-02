"""Provider adapters connecting pykit-messaging to the pykit provider pattern.

Once messaging components are expressed as providers (Sink, Stream),
they compose naturally with all other kit patterns that accept providers:
DAG, Worker, Pipeline, etc.

Install provider bridge dependencies with::

    pip install pykit-messaging[bridges]
"""

from __future__ import annotations

__all__: list[str] = []

try:
    from pykit_messaging.bridge.provider import ConsumerStream, ProducerSink

    __all__ += ["ConsumerStream", "ProducerSink"]
except ImportError:
    pass
