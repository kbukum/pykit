"""Tests for conversation memory."""

from __future__ import annotations

import pytest

from pykit_agent.memory import InMemoryStore, Memory, SlidingWindowMemory
from pykit_llm.types import Message, user


class TestInMemoryStore:
    """InMemoryStore basic operations."""

    async def test_load_empty(self) -> None:
        store = InMemoryStore()
        assert await store.load("s1") == []

    async def test_save_and_load(self) -> None:
        store = InMemoryStore()
        msgs: list[Message] = [user("hello"), user("world")]
        await store.save("s1", msgs)
        loaded = await store.load("s1")
        assert len(loaded) == 2

    async def test_save_overwrites(self) -> None:
        store = InMemoryStore()
        await store.save("s1", [user("a")])
        await store.save("s1", [user("b"), user("c")])
        loaded = await store.load("s1")
        assert len(loaded) == 2

    async def test_append(self) -> None:
        store = InMemoryStore()
        await store.save("s1", [user("a")])
        await store.append("s1", [user("b")])
        loaded = await store.load("s1")
        assert len(loaded) == 2

    async def test_append_to_empty(self) -> None:
        store = InMemoryStore()
        await store.append("s1", [user("x")])
        loaded = await store.load("s1")
        assert len(loaded) == 1

    async def test_clear(self) -> None:
        store = InMemoryStore()
        await store.save("s1", [user("a")])
        await store.clear("s1")
        assert await store.load("s1") == []

    async def test_clear_nonexistent(self) -> None:
        store = InMemoryStore()
        await store.clear("nope")  # should not raise

    async def test_isolation(self) -> None:
        store = InMemoryStore()
        await store.save("s1", [user("a")])
        await store.save("s2", [user("b"), user("c")])
        assert len(await store.load("s1")) == 1
        assert len(await store.load("s2")) == 2

    async def test_save_copies_list(self) -> None:
        store = InMemoryStore()
        msgs: list[Message] = [user("a")]
        await store.save("s1", msgs)
        msgs.append(user("b"))
        assert len(await store.load("s1")) == 1

    async def test_load_returns_copy(self) -> None:
        store = InMemoryStore()
        await store.save("s1", [user("a")])
        loaded = await store.load("s1")
        loaded.append(user("b"))
        assert len(await store.load("s1")) == 1

    async def test_satisfies_memory_protocol(self) -> None:
        assert isinstance(InMemoryStore(), Memory)


class TestSlidingWindowMemory:
    """SlidingWindowMemory windowing behaviour."""

    async def test_load_within_window(self) -> None:
        store = InMemoryStore()
        await store.save("s1", [user("a"), user("b")])
        window = SlidingWindowMemory(store, max_messages=5)
        loaded = await window.load("s1")
        assert len(loaded) == 2

    async def test_load_truncates(self) -> None:
        store = InMemoryStore()
        msgs: list[Message] = [user(f"m{i}") for i in range(10)]
        await store.save("s1", msgs)
        window = SlidingWindowMemory(store, max_messages=3)
        loaded = await window.load("s1")
        assert len(loaded) == 3

    async def test_save_trims(self) -> None:
        store = InMemoryStore()
        window = SlidingWindowMemory(store, max_messages=2)
        msgs: list[Message] = [user("a"), user("b"), user("c")]
        await window.save("s1", msgs)
        # Underlying store should only have 2
        loaded = await store.load("s1")
        assert len(loaded) == 2

    async def test_append_trims(self) -> None:
        store = InMemoryStore()
        window = SlidingWindowMemory(store, max_messages=3)
        await window.save("s1", [user("a"), user("b"), user("c")])
        await window.append("s1", [user("d")])
        loaded = await window.load("s1")
        assert len(loaded) == 3

    async def test_clear(self) -> None:
        store = InMemoryStore()
        window = SlidingWindowMemory(store, max_messages=5)
        await window.save("s1", [user("a")])
        await window.clear("s1")
        assert await window.load("s1") == []

    def test_invalid_max_messages(self) -> None:
        with pytest.raises(ValueError, match="max_messages must be >= 1"):
            SlidingWindowMemory(InMemoryStore(), max_messages=0)

    async def test_satisfies_memory_protocol(self) -> None:
        store = InMemoryStore()
        window = SlidingWindowMemory(store, max_messages=5)
        assert isinstance(window, Memory)
