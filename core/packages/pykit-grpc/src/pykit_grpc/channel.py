"""Managed gRPC async channel wrapper."""

from __future__ import annotations

import grpc
from grpc import aio

from pykit_grpc.config import GrpcConfig


class GrpcChannel:
    """Wraps a :class:`grpc.aio.Channel` with lifecycle helpers.

    Creates an insecure or secure channel based on *config* and exposes
    connectivity checks and clean shutdown.
    """

    def __init__(self, config: GrpcConfig) -> None:
        self._config = config
        options: list[tuple[str, int]] = [
            ("grpc.max_send_message_length", config.max_message_size),
            ("grpc.max_receive_message_length", config.max_message_size),
            ("grpc.keepalive_time_ms", int(config.keepalive_time * 1000)),
            ("grpc.keepalive_timeout_ms", int(config.keepalive_timeout * 1000)),
        ]
        if config.insecure:
            self._channel: aio.Channel = aio.insecure_channel(config.target, options=options)
        else:
            credentials = grpc.ssl_channel_credentials()
            self._channel = aio.secure_channel(config.target, credentials, options=options)

    @property
    def channel(self) -> aio.Channel:
        """Return the underlying :class:`grpc.aio.Channel`."""
        return self._channel

    async def close(self) -> None:
        """Close the channel gracefully."""
        await self._channel.close()

    async def ping(self) -> bool:
        """Return *True* if the channel is in a connected / ready state."""
        state = self._channel.get_state(try_to_connect=True)
        return bool(state == grpc.ChannelConnectivity.READY)
