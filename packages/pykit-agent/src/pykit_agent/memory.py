"""Conversation memory — persist and window message histories."""

from __future__ import annotations

import asyncio
from typing import Protocol, runtime_checkable

from pykit_llm.types import Message


@runtime_checkable
class Memory(Protocol):
    """Protocol for conversation memory backends."""

    async def load(self, session_id: str) -> list[Message]: ...
    async def save(self, session_id: str, messages: list[Message]) -> None: ...
    async def append(self, session_id: str, messages: list[Message]) -> None: ...
    async def clear(self, session_id: str) -> None: ...


class InMemoryStore:
    """Thread-safe in-memory conversation store.

    Suitable for development, testing, and single-process deployments.
    """

    def __init__(self) -> None:
        self._store: dict[str, list[Message]] = {}
        self._lock = asyncio.Lock()

    async def load(self, session_id: str) -> list[Message]:
        async with self._lock:
            return list(self._store.get(session_id, []))

    async def save(self, session_id: str, messages: list[Message]) -> None:
        async with self._lock:
            self._store[session_id] = list(messages)

    async def save_many(self, sessions: dict[str, list[Message]]) -> None:
        """Bulk-save multiple sessions."""
        async with self._lock:
            for sid, msgs in sessions.items():
                self._store[sid] = list(msgs)

    async def append(self, session_id: str, messages: list[Message]) -> None:
        async with self._lock:
            self._store.setdefault(session_id, []).extend(messages)

    async def clear(self, session_id: str) -> None:
        async with self._lock:
            self._store.pop(session_id, None)


class SlidingWindowMemory:
    """Wraps any :class:`Memory` with a sliding window of *max_messages*.

    On :meth:`load`, the returned list is truncated to the most recent
    *max_messages* entries.  On :meth:`save` / :meth:`append`, the store
    is trimmed after the write so that subsequent loads stay within the
    window.
    """

    def __init__(self, store: Memory, max_messages: int) -> None:
        if max_messages < 1:
            raise ValueError("max_messages must be >= 1")
        self._store = store
        self._max = max_messages

    async def load(self, session_id: str) -> list[Message]:
        msgs = await self._store.load(session_id)
        return msgs[-self._max :] if len(msgs) > self._max else msgs

    async def save(self, session_id: str, messages: list[Message]) -> None:
        trimmed = messages[-self._max :] if len(messages) > self._max else messages
        await self._store.save(session_id, trimmed)

    async def append(self, session_id: str, messages: list[Message]) -> None:
        await self._store.append(session_id, messages)
        # Trim after append
        all_msgs = await self._store.load(session_id)
        if len(all_msgs) > self._max:
            await self._store.save(session_id, all_msgs[-self._max :])

    async def clear(self, session_id: str) -> None:
        await self._store.clear(session_id)
