"""Extended tests for pykit_sse — edge cases, concurrency, and stress."""

from __future__ import annotations

import asyncio

import pytest

from pykit_sse import SSEClient, SSEComponent, SSEEvent, SSEHub

# ---------------------------------------------------------------------------
# Filter function edge cases
# ---------------------------------------------------------------------------


class TestFilterEdgeCases:
    @pytest.mark.asyncio
    async def test_broadcast_with_none_filter(self) -> None:
        """None filter should broadcast to all clients."""
        hub = SSEHub()
        c1 = SSEClient("c1")
        c2 = SSEClient("c2")
        hub.register(c1)
        hub.register(c2)

        await hub.broadcast(SSEEvent(data="all"), filter_fn=None)

        assert (await c1.receive()).data == "all"
        assert (await c2.receive()).data == "all"

    @pytest.mark.asyncio
    async def test_broadcast_with_filter_that_raises(self) -> None:
        """A filter that raises should propagate the exception."""
        hub = SSEHub()
        c1 = SSEClient("c1")
        hub.register(c1)

        def bad_filter(_client: SSEClient) -> bool:
            raise ValueError("filter exploded")

        with pytest.raises(ValueError, match="filter exploded"):
            await hub.broadcast(SSEEvent(data="x"), filter_fn=bad_filter)

    @pytest.mark.asyncio
    async def test_broadcast_filter_returns_false_for_all(self) -> None:
        """Filter rejecting everyone means no one receives the event."""
        hub = SSEHub()
        c1 = SSEClient("c1")
        c2 = SSEClient("c2")
        hub.register(c1)
        hub.register(c2)

        await hub.broadcast(SSEEvent(data="reject"), filter_fn=lambda _: False)

        assert c1.queue.empty()
        assert c2.queue.empty()

    @pytest.mark.asyncio
    async def test_broadcast_filter_with_metadata(self) -> None:
        """Filter based on complex metadata conditions."""
        hub = SSEHub()
        c1 = SSEClient("c1", metadata={"role": "admin", "active": True})
        c2 = SSEClient("c2", metadata={"role": "user", "active": True})
        c3 = SSEClient("c3", metadata={"role": "admin", "active": False})
        hub.register(c1)
        hub.register(c2)
        hub.register(c3)

        await hub.broadcast(
            SSEEvent(data="active admins"),
            filter_fn=lambda c: c.metadata.get("role") == "admin"
            and c.metadata.get("active") is True,
        )

        assert (await c1.receive()).data == "active admins"
        assert c2.queue.empty()
        assert c3.queue.empty()


# ---------------------------------------------------------------------------
# Backpressure / slow subscribers
# ---------------------------------------------------------------------------


class TestBackpressure:
    @pytest.mark.asyncio
    async def test_slow_subscriber_queue_buildup(self) -> None:
        """Events accumulate in the queue when client doesn't consume."""
        hub = SSEHub()
        slow = SSEClient("slow")
        hub.register(slow)

        for i in range(100):
            await hub.broadcast(SSEEvent(data=str(i)))

        assert slow.queue.qsize() == 100

        # Drain and verify order
        for i in range(100):
            e = await slow.receive()
            assert e.data == str(i)

    @pytest.mark.asyncio
    async def test_fast_and_slow_subscribers(self) -> None:
        """Fast subscriber should not be affected by slow subscriber."""
        hub = SSEHub()
        fast = SSEClient("fast")
        slow = SSEClient("slow")
        hub.register(fast)
        hub.register(slow)

        await hub.broadcast(SSEEvent(data="msg1"))
        await hub.broadcast(SSEEvent(data="msg2"))

        # Fast reads immediately
        e1 = await fast.receive()
        e2 = await fast.receive()
        assert e1.data == "msg1"
        assert e2.data == "msg2"

        # Slow reads later — still gets both
        e1 = await slow.receive()
        e2 = await slow.receive()
        assert e1.data == "msg1"
        assert e2.data == "msg2"


# ---------------------------------------------------------------------------
# Shutdown during active broadcasts
# ---------------------------------------------------------------------------


class TestShutdownDuringBroadcast:
    @pytest.mark.asyncio
    async def test_shutdown_clears_all_clients(self) -> None:
        """Shutdown should close and clear all clients."""
        hub = SSEHub()
        clients = [SSEClient(f"c{i}") for i in range(10)]
        for c in clients:
            hub.register(c)

        await hub.shutdown()

        assert hub.client_count == 0
        for c in clients:
            assert c.closed

    @pytest.mark.asyncio
    async def test_broadcast_after_shutdown(self) -> None:
        """Broadcast after shutdown is a no-op (no clients)."""
        hub = SSEHub()
        c = SSEClient("c1")
        hub.register(c)

        await hub.shutdown()
        # Broadcast to empty hub should not raise
        await hub.broadcast(SSEEvent(data="ghost"))

    @pytest.mark.asyncio
    async def test_send_to_closed_client_is_ignored(self) -> None:
        """Sending to a closed client should be silently ignored."""
        c = SSEClient("c1")
        c.close()
        assert c.closed

        await c.send(SSEEvent(data="nope"))
        assert c.queue.empty()


# ---------------------------------------------------------------------------
# Client disconnect detection
# ---------------------------------------------------------------------------


class TestClientDisconnect:
    @pytest.mark.asyncio
    async def test_unregister_closes_client(self) -> None:
        hub = SSEHub()
        c = SSEClient("c1")
        hub.register(c)
        assert not c.closed

        hub.unregister("c1")
        assert c.closed
        assert hub.client_count == 0

    @pytest.mark.asyncio
    async def test_double_unregister_is_safe(self) -> None:
        hub = SSEHub()
        c = SSEClient("c1")
        hub.register(c)

        hub.unregister("c1")
        hub.unregister("c1")  # second unregister should not raise
        assert hub.client_count == 0


# ---------------------------------------------------------------------------
# Event ordering guarantees
# ---------------------------------------------------------------------------


class TestEventOrdering:
    @pytest.mark.asyncio
    async def test_broadcast_order_preserved(self) -> None:
        """Events broadcast in sequence should arrive in the same order."""
        hub = SSEHub()
        c = SSEClient("c1")
        hub.register(c)

        for i in range(50):
            await hub.broadcast(SSEEvent(data=str(i)))

        for i in range(50):
            e = await c.receive()
            assert e.data == str(i)

    @pytest.mark.asyncio
    async def test_send_to_order_preserved(self) -> None:
        """Direct sends should preserve order."""
        hub = SSEHub()
        c = SSEClient("c1")
        hub.register(c)

        for i in range(50):
            await hub.send_to("c1", SSEEvent(data=str(i)))

        for i in range(50):
            e = await c.receive()
            assert e.data == str(i)


# ---------------------------------------------------------------------------
# Large number of concurrent subscribers
# ---------------------------------------------------------------------------


class TestManySubscribers:
    @pytest.mark.asyncio
    async def test_100_concurrent_subscribers(self) -> None:
        """Broadcast to 100+ subscribers should deliver to all."""
        hub = SSEHub()
        clients = [SSEClient(f"c{i}") for i in range(120)]
        for c in clients:
            hub.register(c)

        assert hub.client_count == 120

        await hub.broadcast(SSEEvent(data="mass"))

        for c in clients:
            e = await c.receive()
            assert e.data == "mass"

    @pytest.mark.asyncio
    async def test_register_unregister_many(self) -> None:
        """Register and unregister many clients rapidly."""
        hub = SSEHub()
        for i in range(200):
            c = SSEClient(f"c{i}")
            hub.register(c)

        assert hub.client_count == 200

        for i in range(200):
            hub.unregister(f"c{i}")

        assert hub.client_count == 0


# ---------------------------------------------------------------------------
# Empty event data, Unicode content
# ---------------------------------------------------------------------------


class TestEventContent:
    def test_encode_empty_data(self) -> None:
        e = SSEEvent(data="")
        encoded = e.encode()
        assert "data: \n" in encoded
        assert encoded.endswith("\n\n")

    def test_encode_unicode(self) -> None:
        e = SSEEvent(data="こんにちは世界 🌍")
        encoded = e.encode()
        assert "data: こんにちは世界 🌍\n" in encoded

    def test_encode_emoji_event_type(self) -> None:
        e = SSEEvent(event="🔔notification", data="ping")
        encoded = e.encode()
        assert "event: 🔔notification\n" in encoded

    def test_encode_newlines_in_data(self) -> None:
        e = SSEEvent(data="line1\nline2\nline3")
        encoded = e.encode()
        # Each line should be a separate data: line
        assert encoded.count("data: ") == 3

    @pytest.mark.asyncio
    async def test_send_receive_unicode(self) -> None:
        c = SSEClient("c1")
        await c.send(SSEEvent(data="日本語テスト"))
        received = await c.receive()
        assert received.data == "日本語テスト"

    def test_encode_with_all_fields(self) -> None:
        e = SSEEvent(event="update", data="payload", id="99", retry=5000)
        encoded = e.encode()
        assert "id: 99\n" in encoded
        assert "event: update\n" in encoded
        assert "retry: 5000\n" in encoded
        assert "data: payload\n" in encoded
        assert encoded.endswith("\n\n")

    def test_encode_id_ordering(self) -> None:
        """id should appear before event per SSE spec."""
        e = SSEEvent(event="custom", data="x", id="1")
        encoded = e.encode()
        id_pos = encoded.index("id:")
        event_pos = encoded.index("event:")
        assert id_pos < event_pos


# ---------------------------------------------------------------------------
# Component lifecycle integration
# ---------------------------------------------------------------------------


class TestComponentExtended:
    @pytest.mark.asyncio
    async def test_stop_during_broadcast(self) -> None:
        """Stopping component while clients exist should clean up."""
        comp = SSEComponent()
        await comp.start()

        clients = [SSEClient(f"c{i}") for i in range(5)]
        for c in clients:
            comp.hub.register(c)

        # Broadcast some events
        await comp.hub.broadcast(SSEEvent(data="before-stop"))

        await comp.stop()

        assert comp.hub.client_count == 0
        for c in clients:
            assert c.closed

    @pytest.mark.asyncio
    async def test_health_reflects_client_count(self) -> None:
        comp = SSEComponent()
        await comp.start()

        h0 = await comp.health()
        assert "0 clients" in h0.message

        for i in range(3):
            comp.hub.register(SSEClient(f"c{i}"))

        h3 = await comp.health()
        assert "3 clients" in h3.message

        await comp.stop()

    @pytest.mark.asyncio
    async def test_double_stop_is_safe(self) -> None:
        comp = SSEComponent()
        await comp.start()
        comp.hub.register(SSEClient("c1"))

        await comp.stop()
        await comp.stop()  # should not raise


# ---------------------------------------------------------------------------
# Concurrent async operations
# ---------------------------------------------------------------------------


class TestConcurrentAsync:
    @pytest.mark.asyncio
    async def test_concurrent_broadcasts(self) -> None:
        """Multiple concurrent broadcasts should all deliver."""
        hub = SSEHub()
        c = SSEClient("c1")
        hub.register(c)

        async def do_broadcast(idx: int) -> None:
            await hub.broadcast(SSEEvent(data=str(idx)))

        await asyncio.gather(*[do_broadcast(i) for i in range(20)])

        received = set()
        for _ in range(20):
            e = await c.receive()
            received.add(e.data)

        assert received == {str(i) for i in range(20)}

    @pytest.mark.asyncio
    async def test_concurrent_register_broadcast_unregister(self) -> None:
        """Mixed concurrent operations should not corrupt state."""
        hub = SSEHub()

        async def churn(idx: int) -> None:
            c = SSEClient(f"churn-{idx}")
            hub.register(c)
            await hub.broadcast(SSEEvent(data=f"msg-{idx}"))
            hub.unregister(f"churn-{idx}")

        await asyncio.gather(*[churn(i) for i in range(30)])

        # Hub should be clean
        assert hub.client_count == 0
