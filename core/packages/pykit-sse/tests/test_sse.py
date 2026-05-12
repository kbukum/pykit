"""Comprehensive tests for pykit_sse."""

from __future__ import annotations

import pytest

from pykit_component import Component, Description, HealthStatus
from pykit_sse import SSEClient, SSEComponent, SSEEvent, SSEHub

# ---------------------------------------------------------------------------
# SSEEvent
# ---------------------------------------------------------------------------


class TestSSEEvent:
    def test_defaults(self) -> None:
        e = SSEEvent()
        assert e.event == "message"
        assert e.data == ""
        assert e.id is None
        assert e.retry is None

    def test_encode_default_message(self) -> None:
        e = SSEEvent(data="hello")
        encoded = e.encode()
        assert "data: hello\n" in encoded
        # default event type "message" should NOT produce an event: line
        assert "event:" not in encoded
        assert encoded.endswith("\n\n")

    def test_encode_custom_event(self) -> None:
        e = SSEEvent(event="update", data="payload")
        encoded = e.encode()
        assert "event: update\n" in encoded
        assert "data: payload\n" in encoded

    def test_encode_with_id(self) -> None:
        e = SSEEvent(data="x", id="42")
        encoded = e.encode()
        assert "id: 42\n" in encoded

    def test_encode_with_retry(self) -> None:
        e = SSEEvent(data="x", retry=3000)
        encoded = e.encode()
        assert "retry: 3000\n" in encoded

    def test_encode_multiline_data(self) -> None:
        e = SSEEvent(data="line1\nline2\nline3")
        encoded = e.encode()
        assert "data: line1\n" in encoded
        assert "data: line2\n" in encoded
        assert "data: line3\n" in encoded

    def test_encode_empty_data(self) -> None:
        e = SSEEvent()
        encoded = e.encode()
        assert "data: \n" in encoded

    def test_encode_full(self) -> None:
        e = SSEEvent(event="error", data="oops", id="7", retry=5000)
        encoded = e.encode()
        assert "id: 7\n" in encoded
        assert "event: error\n" in encoded
        assert "retry: 5000\n" in encoded
        assert "data: oops\n" in encoded


# ---------------------------------------------------------------------------
# SSEClient
# ---------------------------------------------------------------------------


class TestSSEClient:
    def test_init_defaults(self) -> None:
        c = SSEClient("c1")
        assert c.client_id == "c1"
        assert c.metadata == {}
        assert not c.closed

    def test_init_with_metadata(self) -> None:
        c = SSEClient("c2", metadata={"role": "admin"})
        assert c.metadata == {"role": "admin"}

    @pytest.mark.asyncio
    async def test_send_receive(self) -> None:
        c = SSEClient("c1")
        event = SSEEvent(data="hi")
        await c.send(event)
        received = await c.receive()
        assert received is event
        assert received.data == "hi"

    @pytest.mark.asyncio
    async def test_send_multiple(self) -> None:
        c = SSEClient("c1")
        for i in range(5):
            await c.send(SSEEvent(data=str(i)))
        for i in range(5):
            e = await c.receive()
            assert e.data == str(i)

    def test_close(self) -> None:
        c = SSEClient("c1")
        assert not c.closed
        c.close()
        assert c.closed

    @pytest.mark.asyncio
    async def test_send_after_close_is_ignored(self) -> None:
        c = SSEClient("c1")
        c.close()
        await c.send(SSEEvent(data="nope"))
        assert c.queue.empty()


# ---------------------------------------------------------------------------
# SSEHub
# ---------------------------------------------------------------------------


class TestSSEHub:
    def test_register(self) -> None:
        hub = SSEHub()
        c = SSEClient("c1")
        hub.register(c)
        assert hub.client_count == 1
        assert hub.get_client("c1") is c

    def test_unregister(self) -> None:
        hub = SSEHub()
        c = SSEClient("c1")
        hub.register(c)
        hub.unregister("c1")
        assert hub.client_count == 0
        assert hub.get_client("c1") is None
        assert c.closed

    def test_unregister_unknown(self) -> None:
        hub = SSEHub()
        hub.unregister("nonexistent")  # should not raise
        assert hub.client_count == 0

    @pytest.mark.asyncio
    async def test_broadcast(self) -> None:
        hub = SSEHub()
        c1 = SSEClient("c1")
        c2 = SSEClient("c2")
        hub.register(c1)
        hub.register(c2)

        event = SSEEvent(data="hello all")
        await hub.broadcast(event)

        r1 = await c1.receive()
        r2 = await c2.receive()
        assert r1.data == "hello all"
        assert r2.data == "hello all"

    @pytest.mark.asyncio
    async def test_broadcast_filtered(self) -> None:
        hub = SSEHub()
        c1 = SSEClient("c1", metadata={"role": "admin"})
        c2 = SSEClient("c2", metadata={"role": "user"})
        hub.register(c1)
        hub.register(c2)

        event = SSEEvent(data="admin only")
        await hub.broadcast(event, filter_fn=lambda c: c.metadata.get("role") == "admin")

        r1 = await c1.receive()
        assert r1.data == "admin only"
        assert c2.queue.empty()

    @pytest.mark.asyncio
    async def test_send_to(self) -> None:
        hub = SSEHub()
        c1 = SSEClient("c1")
        c2 = SSEClient("c2")
        hub.register(c1)
        hub.register(c2)

        event = SSEEvent(data="just for c2")
        await hub.send_to("c2", event)

        assert c1.queue.empty()
        r2 = await c2.receive()
        assert r2.data == "just for c2"

    @pytest.mark.asyncio
    async def test_send_to_unknown_raises(self) -> None:
        hub = SSEHub()
        with pytest.raises(KeyError, match="client 'missing' not registered"):
            await hub.send_to("missing", SSEEvent(data="x"))

    def test_get_client_missing(self) -> None:
        hub = SSEHub()
        assert hub.get_client("nope") is None

    @pytest.mark.asyncio
    async def test_shutdown(self) -> None:
        hub = SSEHub()
        c1 = SSEClient("c1")
        c2 = SSEClient("c2")
        hub.register(c1)
        hub.register(c2)

        await hub.shutdown()

        assert hub.client_count == 0
        assert c1.closed
        assert c2.closed

    @pytest.mark.asyncio
    async def test_broadcast_empty_hub(self) -> None:
        hub = SSEHub()
        await hub.broadcast(SSEEvent(data="no one listening"))  # should not raise


# ---------------------------------------------------------------------------
# SSEComponent
# ---------------------------------------------------------------------------


class TestSSEComponent:
    def test_satisfies_component_protocol(self) -> None:
        comp = SSEComponent()
        assert isinstance(comp, Component)

    def test_satisfies_describable_protocol(self) -> None:
        comp = SSEComponent()
        desc = comp.describe()
        assert isinstance(desc, Description)

    def test_name(self) -> None:
        comp = SSEComponent()
        assert comp.name == "sse"

    def test_hub_accessible(self) -> None:
        comp = SSEComponent()
        assert isinstance(comp.hub, SSEHub)

    @pytest.mark.asyncio
    async def test_start_stop(self) -> None:
        comp = SSEComponent()
        await comp.start()
        await comp.stop()

    @pytest.mark.asyncio
    async def test_health(self) -> None:
        comp = SSEComponent()
        h = await comp.health()
        assert h.name == "sse"
        assert h.status == HealthStatus.HEALTHY
        assert "0 clients" in h.message

    @pytest.mark.asyncio
    async def test_health_with_clients(self) -> None:
        comp = SSEComponent()
        await comp.start()
        comp.hub.register(SSEClient("c1"))
        comp.hub.register(SSEClient("c2"))

        h = await comp.health()
        assert "2 clients" in h.message
        await comp.stop()

    def test_describe(self) -> None:
        comp = SSEComponent(path="/api/events")
        desc = comp.describe()
        assert desc.name == "SSE Hub"
        assert desc.type == "sse"
        assert "/api/events" in desc.details

    @pytest.mark.asyncio
    async def test_stop_closes_clients(self) -> None:
        comp = SSEComponent()
        await comp.start()
        c = SSEClient("c1")
        comp.hub.register(c)

        await comp.stop()

        assert comp.hub.client_count == 0
        assert c.closed
