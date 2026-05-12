"""Test assertion helpers for the in-memory message broker."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from pykit_messaging.memory import InMemoryBroker
from pykit_messaging.types import Message


def assert_published(
    broker: InMemoryBroker,
    topic: str,
    predicate: Callable[[Message], bool],
) -> None:
    """Assert that at least one message on *topic* satisfies *predicate*.

    Args:
        broker: The in-memory broker to inspect.
        topic: Topic name.
        predicate: A callable that returns ``True`` for the expected message.

    Raises:
        AssertionError: When no matching message is found.
    """
    msgs = broker.messages(topic)
    for msg in msgs:
        if predicate(msg):
            return
    raise AssertionError(
        f"assert_published: no message on topic {topic!r} matched the predicate ({len(msgs)} checked)"
    )


def assert_published_n(broker: InMemoryBroker, topic: str, n: int) -> None:
    """Assert that exactly *n* messages were published to *topic*.

    Args:
        broker: The in-memory broker to inspect.
        topic: Topic name.
        n: Expected number of messages.

    Raises:
        AssertionError: When the count does not match.
    """
    got = broker.message_count(topic)
    if got != n:
        raise AssertionError(f"assert_published_n: topic {topic!r} has {got} messages, want {n}")


async def wait_for_message(
    broker: InMemoryBroker,
    topic: str,
    timeout: float,
) -> Message:
    """Wait until at least one message appears on *topic*.

    Args:
        broker: The in-memory broker to inspect.
        topic: Topic name.
        timeout: Maximum seconds to wait.

    Returns:
        The first message on the topic.

    Raises:
        TimeoutError: When the deadline elapses before a message arrives.
    """
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        msgs = broker.messages(topic)
        if msgs:
            return msgs[0]
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            raise TimeoutError(
                f"wait_for_message: timed out after {timeout}s waiting for message on topic {topic!r}"
            )
        await asyncio.sleep(min(0.01, remaining))


def assert_no_messages(broker: InMemoryBroker, topic: str) -> None:
    """Assert that zero messages were published to *topic*.

    Args:
        broker: The in-memory broker to inspect.
        topic: Topic name.

    Raises:
        AssertionError: When the topic is not empty.
    """
    n = broker.message_count(topic)
    if n != 0:
        raise AssertionError(f"assert_no_messages: topic {topic!r} has {n} messages, want 0")
