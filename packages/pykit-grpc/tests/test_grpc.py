"""Tests for pykit-grpc — config, errors, channel, and component lifecycle."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import grpc

from pykit_component import Health, HealthStatus
from pykit_errors import AppError, InvalidInputError, NotFoundError, ServiceUnavailableError
from pykit_errors.base import TimeoutError as AppTimeoutError
from pykit_errors.codes import ErrorCode
from pykit_grpc import (
    GrpcChannel,
    GrpcComponent,
    GrpcConfig,
    app_error_to_grpc_status,
    app_error_to_grpc_trailing_metadata,
    grpc_error_to_app_error,
)

# ── Config defaults ────────────────────────────────────────────────────


class TestGrpcConfig:
    def test_defaults(self) -> None:
        cfg = GrpcConfig()
        assert cfg.target == "localhost:50051"
        assert cfg.insecure is True
        assert cfg.timeout == 30.0
        assert cfg.max_message_size == 4 * 1024 * 1024
        assert cfg.keepalive_time == 30.0
        assert cfg.keepalive_timeout == 10.0

    def test_custom_values(self) -> None:
        cfg = GrpcConfig(
            target="remote:9090",
            insecure=False,
            timeout=10.0,
            max_message_size=8 * 1024 * 1024,
            keepalive_time=60.0,
            keepalive_timeout=20.0,
        )
        assert cfg.target == "remote:9090"
        assert cfg.insecure is False
        assert cfg.timeout == 10.0
        assert cfg.max_message_size == 8 * 1024 * 1024
        assert cfg.keepalive_time == 60.0
        assert cfg.keepalive_timeout == 20.0


# ── Error mapping: gRPC → AppError ─────────────────────────────────────


def _make_rpc_error(code: grpc.StatusCode, details: str = "") -> grpc.RpcError:
    err = MagicMock()
    err.code.return_value = code
    err.details.return_value = details
    return err


class TestGrpcErrorToAppError:
    def test_not_found(self) -> None:
        err = grpc_error_to_app_error(_make_rpc_error(grpc.StatusCode.NOT_FOUND, "user"))
        assert isinstance(err, NotFoundError)
        assert "user" in str(err)

    def test_invalid_argument(self) -> None:
        err = grpc_error_to_app_error(_make_rpc_error(grpc.StatusCode.INVALID_ARGUMENT, "bad field"))
        assert isinstance(err, InvalidInputError)
        assert "bad field" in str(err)

    def test_unavailable(self) -> None:
        err = grpc_error_to_app_error(_make_rpc_error(grpc.StatusCode.UNAVAILABLE, "backend"))
        assert isinstance(err, ServiceUnavailableError)
        assert "backend" in str(err)

    def test_deadline_exceeded(self) -> None:
        err = grpc_error_to_app_error(_make_rpc_error(grpc.StatusCode.DEADLINE_EXCEEDED, "slow-op"))
        assert isinstance(err, AppTimeoutError)
        assert "slow-op" in str(err)

    def test_unknown_code_falls_back(self) -> None:
        err = grpc_error_to_app_error(_make_rpc_error(grpc.StatusCode.DATA_LOSS, "oops"))
        assert isinstance(err, AppError)
        assert not isinstance(err, NotFoundError)

    def test_empty_details_not_found(self) -> None:
        err = grpc_error_to_app_error(_make_rpc_error(grpc.StatusCode.NOT_FOUND))
        assert isinstance(err, NotFoundError)

    def test_empty_details_unavailable(self) -> None:
        err = grpc_error_to_app_error(_make_rpc_error(grpc.StatusCode.UNAVAILABLE))
        assert isinstance(err, ServiceUnavailableError)


# ── Error mapping: AppError → gRPC status ──────────────────────────────


class TestAppErrorToGrpcStatus:
    def test_not_found(self) -> None:
        code, msg = app_error_to_grpc_status(NotFoundError("thing", "123"))
        assert code == grpc.StatusCode.NOT_FOUND
        assert "thing" in msg

    def test_invalid_input(self) -> None:
        code, _ = app_error_to_grpc_status(InvalidInputError("nope"))
        assert code == grpc.StatusCode.INVALID_ARGUMENT

    def test_unavailable(self) -> None:
        code, _ = app_error_to_grpc_status(ServiceUnavailableError("db"))
        assert code == grpc.StatusCode.UNAVAILABLE

    def test_timeout(self) -> None:
        code, _ = app_error_to_grpc_status(AppTimeoutError("query", 5.0))
        assert code == grpc.StatusCode.DEADLINE_EXCEEDED

    def test_generic_app_error(self) -> None:
        code, msg = app_error_to_grpc_status(AppError(ErrorCode.INTERNAL, "boom"))
        assert code == grpc.StatusCode.INTERNAL
        assert "boom" in msg


# ── Trailing metadata with ProblemDetail ───────────────────────────────


class TestAppErrorToGrpcTrailingMetadata:
    def test_returns_x_error_details_bin(self) -> None:
        err = AppError.not_found("User", "u-1")
        metadata = app_error_to_grpc_trailing_metadata(err)
        assert len(metadata) == 1
        key, value = metadata[0]
        assert key == "x-error-details-bin"
        assert isinstance(value, bytes)

    def test_payload_is_valid_problem_detail_json(self) -> None:
        err = AppError.not_found("User", "u-1")
        _, payload = app_error_to_grpc_trailing_metadata(err)[0]
        body = json.loads(payload)
        assert body["type"] == "https://pykit.dev/errors/not-found"
        assert body["title"] == "Not Found"
        assert body["status"] == 404
        assert body["code"] == "NOT_FOUND"
        assert body["retryable"] is False
        assert "detail" in body

    def test_instance_embedded_when_provided(self) -> None:
        err = AppError.not_found("User", "u-1")
        _, payload = app_error_to_grpc_trailing_metadata(err, instance="/users/u-1")[0]
        body = json.loads(payload)
        assert body["instance"] == "/users/u-1"

    def test_instance_omitted_when_empty(self) -> None:
        err = AppError(ErrorCode.INTERNAL, "oops")
        _, payload = app_error_to_grpc_trailing_metadata(err)[0]
        body = json.loads(payload)
        assert "instance" not in body

    def test_details_embedded(self) -> None:
        err = AppError.not_found("Widget", "w-99")
        _, payload = app_error_to_grpc_trailing_metadata(err)[0]
        body = json.loads(payload)
        assert body["details"] == {"resource": "Widget"}


# ── Channel (mocked grpc.aio) ──────────────────────────────────────────


class TestGrpcChannel:
    @patch("pykit_grpc.channel.aio")
    def test_insecure_channel_created(self, mock_aio: MagicMock) -> None:
        cfg = GrpcConfig(target="localhost:50051", insecure=True)
        ch = GrpcChannel(cfg)
        mock_aio.insecure_channel.assert_called_once()
        assert ch.channel is mock_aio.insecure_channel.return_value

    @patch("pykit_grpc.channel.aio")
    @patch("pykit_grpc.channel.grpc.ssl_channel_credentials")
    def test_secure_channel_created(self, mock_creds: MagicMock, mock_aio: MagicMock) -> None:
        cfg = GrpcConfig(target="remote:443", insecure=False)
        ch = GrpcChannel(cfg)
        mock_aio.secure_channel.assert_called_once()
        assert ch.channel is mock_aio.secure_channel.return_value

    @patch("pykit_grpc.channel.aio")
    async def test_close(self, mock_aio: MagicMock) -> None:
        mock_channel = AsyncMock()
        mock_aio.insecure_channel.return_value = mock_channel
        ch = GrpcChannel(GrpcConfig())
        await ch.close()
        mock_channel.close.assert_awaited_once()

    @patch("pykit_grpc.channel.aio")
    async def test_ping_ready(self, mock_aio: MagicMock) -> None:
        mock_channel = MagicMock()
        mock_channel.get_state.return_value = grpc.ChannelConnectivity.READY
        mock_aio.insecure_channel.return_value = mock_channel
        ch = GrpcChannel(GrpcConfig())
        assert await ch.ping() is True

    @patch("pykit_grpc.channel.aio")
    async def test_ping_not_ready(self, mock_aio: MagicMock) -> None:
        mock_channel = MagicMock()
        mock_channel.get_state.return_value = grpc.ChannelConnectivity.IDLE
        mock_aio.insecure_channel.return_value = mock_channel
        ch = GrpcChannel(GrpcConfig())
        assert await ch.ping() is False


# ── Component lifecycle (mocked) ───────────────────────────────────────


class TestGrpcComponent:
    def test_name(self) -> None:
        comp = GrpcComponent(GrpcConfig(), component_name="my-grpc")
        assert comp.name == "my-grpc"

    async def test_start_creates_channel(self) -> None:
        comp = GrpcComponent(GrpcConfig())
        assert comp.grpc_channel is None
        with patch("pykit_grpc.component.GrpcChannel"):
            await comp.start()
        assert comp.grpc_channel is not None

    async def test_stop_closes_channel(self) -> None:
        comp = GrpcComponent(GrpcConfig())
        mock_channel = AsyncMock()
        with patch("pykit_grpc.component.GrpcChannel", return_value=mock_channel):
            await comp.start()
            await comp.stop()
        mock_channel.close.assert_awaited_once()
        assert comp.grpc_channel is None

    async def test_stop_before_start_is_noop(self) -> None:
        comp = GrpcComponent(GrpcConfig())
        await comp.stop()  # should not raise

    async def test_health_before_start(self) -> None:
        comp = GrpcComponent(GrpcConfig())
        h = await comp.health()
        assert isinstance(h, Health)
        assert h.status == HealthStatus.UNHEALTHY

    async def test_health_connected(self) -> None:
        comp = GrpcComponent(GrpcConfig())
        mock_channel = AsyncMock()
        mock_channel.ping = AsyncMock(return_value=True)
        with patch("pykit_grpc.component.GrpcChannel", return_value=mock_channel):
            await comp.start()
        h = await comp.health()
        assert h.status == HealthStatus.HEALTHY

    async def test_health_not_connected(self) -> None:
        comp = GrpcComponent(GrpcConfig())
        mock_channel = AsyncMock()
        mock_channel.ping = AsyncMock(return_value=False)
        with patch("pykit_grpc.component.GrpcChannel", return_value=mock_channel):
            await comp.start()
        h = await comp.health()
        assert h.status == HealthStatus.DEGRADED

    async def test_health_ping_raises(self) -> None:
        comp = GrpcComponent(GrpcConfig())
        mock_channel = AsyncMock()
        mock_channel.ping = AsyncMock(side_effect=RuntimeError("network"))
        with patch("pykit_grpc.component.GrpcChannel", return_value=mock_channel):
            await comp.start()
        h = await comp.health()
        assert h.status == HealthStatus.UNHEALTHY
        assert "network" in h.message
