"""Tests for pykit_server.interceptors — LoggingInterceptor, ErrorHandlingInterceptor, MetricsInterceptor."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import grpc
import pytest

from pykit_errors import AppError, NotFoundError
from pykit_server.interceptors import (
    ErrorHandlingInterceptor,
    LoggingInterceptor,
    MetricsInterceptor,
)

# ---------------------------------------------------------------------------
# Helpers to build fake gRPC handler / call-details objects
# ---------------------------------------------------------------------------


def _make_handler(
    *,
    unary_unary: Any = None,
    request_deserializer: Any = None,
    response_serializer: Any = None,
) -> MagicMock:
    handler = MagicMock()
    handler.unary_unary = unary_unary
    handler.request_deserializer = request_deserializer
    handler.response_serializer = response_serializer
    return handler


def _make_call_details(method: str = "/pkg.Service/Method") -> MagicMock:
    details = MagicMock(spec=grpc.HandlerCallDetails)
    details.method = method
    return details


# ---------------------------------------------------------------------------
# LoggingInterceptor
# ---------------------------------------------------------------------------


class TestLoggingInterceptor:
    @pytest.mark.asyncio
    async def test_returns_none_when_handler_is_none(self) -> None:
        interceptor = LoggingInterceptor()
        continuation = AsyncMock(return_value=None)
        details = _make_call_details()

        result = await interceptor.intercept_service(continuation, details)

        assert result is None
        continuation.assert_awaited_once_with(details)

    @pytest.mark.asyncio
    async def test_returns_handler_when_no_unary_unary(self) -> None:
        handler = _make_handler(unary_unary=None)
        interceptor = LoggingInterceptor()
        continuation = AsyncMock(return_value=handler)
        details = _make_call_details()

        result = await interceptor.intercept_service(continuation, details)

        assert result is handler

    @pytest.mark.asyncio
    async def test_wraps_unary_unary_on_success(self) -> None:
        sentinel_response = object()
        original_fn = AsyncMock(return_value=sentinel_response)
        handler = _make_handler(unary_unary=original_fn)
        interceptor = LoggingInterceptor()
        continuation = AsyncMock(return_value=handler)
        details = _make_call_details("/svc/OK")

        with patch("pykit_server.interceptors.grpc.unary_unary_rpc_method_handler") as mock_wrap:
            mock_wrap.side_effect = lambda fn, **kw: MagicMock(unary_unary=fn)
            wrapped = await interceptor.intercept_service(continuation, details)

        # Invoke the wrapped handler
        ctx = AsyncMock()
        req = object()
        resp = await wrapped.unary_unary(req, ctx)

        assert resp is sentinel_response
        original_fn.assert_awaited_once_with(req, ctx)

    @pytest.mark.asyncio
    async def test_wraps_unary_unary_on_failure(self) -> None:
        original_fn = AsyncMock(side_effect=RuntimeError("boom"))
        handler = _make_handler(unary_unary=original_fn)
        interceptor = LoggingInterceptor()
        continuation = AsyncMock(return_value=handler)
        details = _make_call_details("/svc/Fail")

        with patch("pykit_server.interceptors.grpc.unary_unary_rpc_method_handler") as mock_wrap:
            mock_wrap.side_effect = lambda fn, **kw: MagicMock(unary_unary=fn)
            wrapped = await interceptor.intercept_service(continuation, details)

        ctx = AsyncMock()
        with pytest.raises(RuntimeError, match="boom"):
            await wrapped.unary_unary(object(), ctx)

    @pytest.mark.asyncio
    async def test_passes_deserializer_and_serializer(self) -> None:
        deser = object()
        ser = object()
        handler = _make_handler(
            unary_unary=AsyncMock(return_value="ok"),
            request_deserializer=deser,
            response_serializer=ser,
        )
        interceptor = LoggingInterceptor()
        continuation = AsyncMock(return_value=handler)
        details = _make_call_details()

        with patch("pykit_server.interceptors.grpc.unary_unary_rpc_method_handler") as mock_wrap:
            mock_wrap.return_value = MagicMock()
            await interceptor.intercept_service(continuation, details)

        mock_wrap.assert_called_once()
        _, kwargs = mock_wrap.call_args
        assert kwargs["request_deserializer"] is deser
        assert kwargs["response_serializer"] is ser


# ---------------------------------------------------------------------------
# ErrorHandlingInterceptor
# ---------------------------------------------------------------------------


class TestErrorHandlingInterceptor:
    @pytest.mark.asyncio
    async def test_returns_none_when_handler_is_none(self) -> None:
        interceptor = ErrorHandlingInterceptor()
        continuation = AsyncMock(return_value=None)
        details = _make_call_details()

        result = await interceptor.intercept_service(continuation, details)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_handler_when_no_unary_unary(self) -> None:
        handler = _make_handler(unary_unary=None)
        interceptor = ErrorHandlingInterceptor()
        continuation = AsyncMock(return_value=handler)
        details = _make_call_details()

        result = await interceptor.intercept_service(continuation, details)

        assert result is handler

    @pytest.mark.asyncio
    async def test_success_path(self) -> None:
        sentinel = object()
        original = AsyncMock(return_value=sentinel)
        handler = _make_handler(unary_unary=original)
        interceptor = ErrorHandlingInterceptor()
        continuation = AsyncMock(return_value=handler)
        details = _make_call_details()

        with patch("pykit_server.interceptors.grpc.unary_unary_rpc_method_handler") as mock_wrap:
            mock_wrap.side_effect = lambda fn, **kw: MagicMock(unary_unary=fn)
            wrapped = await interceptor.intercept_service(continuation, details)

        ctx = AsyncMock()
        resp = await wrapped.unary_unary(object(), ctx)

        assert resp is sentinel
        ctx.abort.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_app_error_aborts_with_grpc_status(self) -> None:
        app_err = NotFoundError("User", "123")
        original = AsyncMock(side_effect=app_err)
        handler = _make_handler(unary_unary=original)
        interceptor = ErrorHandlingInterceptor()
        continuation = AsyncMock(return_value=handler)
        details = _make_call_details()

        with patch("pykit_server.interceptors.grpc.unary_unary_rpc_method_handler") as mock_wrap:
            mock_wrap.side_effect = lambda fn, **kw: MagicMock(unary_unary=fn)
            wrapped = await interceptor.intercept_service(continuation, details)

        ctx = AsyncMock()
        await wrapped.unary_unary(object(), ctx)

        ctx.abort.assert_awaited_once_with(grpc.StatusCode.NOT_FOUND, app_err.message)

    @pytest.mark.asyncio
    async def test_app_error_sets_trailing_metadata(self) -> None:
        import json

        app_err = AppError.not_found("User", "123")
        original = AsyncMock(side_effect=app_err)
        handler = _make_handler(unary_unary=original)
        interceptor = ErrorHandlingInterceptor()
        continuation = AsyncMock(return_value=handler)
        details = _make_call_details()

        with patch("pykit_server.interceptors.grpc.unary_unary_rpc_method_handler") as mock_wrap:
            mock_wrap.side_effect = lambda fn, **kw: MagicMock(unary_unary=fn)
            wrapped = await interceptor.intercept_service(continuation, details)

        ctx = AsyncMock()
        await wrapped.unary_unary(object(), ctx)

        ctx.set_trailing_metadata.assert_called_once()
        metadata = ctx.set_trailing_metadata.call_args[0][0]
        key, raw = metadata[0]
        assert key == "x-error-details-bin"
        parsed = json.loads(raw.decode("utf-8"))
        assert parsed["code"] == "NOT_FOUND"
        assert parsed["message"] == app_err.message
        assert parsed["retryable"] is False
        assert parsed["details"] == {"resource": "User"}

    @pytest.mark.filterwarnings("ignore::UserWarning")
    @pytest.mark.asyncio
    async def test_unexpected_error_aborts_internal(self) -> None:
        original = AsyncMock(side_effect=ValueError("unexpected"))
        handler = _make_handler(unary_unary=original)
        interceptor = ErrorHandlingInterceptor()
        continuation = AsyncMock(return_value=handler)
        details = _make_call_details()

        with patch("pykit_server.interceptors.grpc.unary_unary_rpc_method_handler") as mock_wrap:
            mock_wrap.side_effect = lambda fn, **kw: MagicMock(unary_unary=fn)
            wrapped = await interceptor.intercept_service(continuation, details)

        ctx = AsyncMock()
        await wrapped.unary_unary(object(), ctx)

        ctx.abort.assert_awaited_once_with(grpc.StatusCode.INTERNAL, "Internal server error")

    @pytest.mark.asyncio
    async def test_passes_deserializer_and_serializer(self) -> None:
        deser = object()
        ser = object()
        handler = _make_handler(
            unary_unary=AsyncMock(return_value="ok"),
            request_deserializer=deser,
            response_serializer=ser,
        )
        interceptor = ErrorHandlingInterceptor()
        continuation = AsyncMock(return_value=handler)
        details = _make_call_details()

        with patch("pykit_server.interceptors.grpc.unary_unary_rpc_method_handler") as mock_wrap:
            mock_wrap.return_value = MagicMock()
            await interceptor.intercept_service(continuation, details)

        _, kwargs = mock_wrap.call_args
        assert kwargs["request_deserializer"] is deser
        assert kwargs["response_serializer"] is ser


# ---------------------------------------------------------------------------
# MetricsInterceptor
# ---------------------------------------------------------------------------


class TestMetricsInterceptor:
    @pytest.mark.asyncio
    async def test_returns_none_when_handler_is_none(self) -> None:
        collector = MagicMock()
        interceptor = MetricsInterceptor(collector=collector)
        continuation = AsyncMock(return_value=None)
        details = _make_call_details()

        result = await interceptor.intercept_service(continuation, details)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_handler_when_no_unary_unary(self) -> None:
        collector = MagicMock()
        handler = _make_handler(unary_unary=None)
        interceptor = MetricsInterceptor(collector=collector)
        continuation = AsyncMock(return_value=handler)
        details = _make_call_details()

        result = await interceptor.intercept_service(continuation, details)

        assert result is handler

    @pytest.mark.asyncio
    async def test_returns_handler_when_no_collector(self) -> None:
        handler = _make_handler(unary_unary=AsyncMock())
        interceptor = MetricsInterceptor(collector=None)
        continuation = AsyncMock(return_value=handler)
        details = _make_call_details()

        result = await interceptor.intercept_service(continuation, details)

        assert result is handler

    @pytest.mark.asyncio
    async def test_observes_ok_on_success(self) -> None:
        sentinel = object()
        original = AsyncMock(return_value=sentinel)
        handler = _make_handler(unary_unary=original)
        collector = MagicMock()
        interceptor = MetricsInterceptor(collector=collector)
        continuation = AsyncMock(return_value=handler)
        details = _make_call_details("/svc/M")

        with patch("pykit_server.interceptors.grpc.unary_unary_rpc_method_handler") as mock_wrap:
            mock_wrap.side_effect = lambda fn, **kw: MagicMock(unary_unary=fn)
            wrapped = await interceptor.intercept_service(continuation, details)

        ctx = AsyncMock()
        resp = await wrapped.unary_unary(object(), ctx)

        assert resp is sentinel
        collector.observe_request.assert_called_once()
        args = collector.observe_request.call_args[0]
        assert args[0] == "/svc/M"
        assert args[1] == "OK"
        assert isinstance(args[2], float)

    @pytest.mark.asyncio
    async def test_observes_error_on_failure(self) -> None:
        original = AsyncMock(side_effect=RuntimeError("fail"))
        handler = _make_handler(unary_unary=original)
        collector = MagicMock()
        interceptor = MetricsInterceptor(collector=collector)
        continuation = AsyncMock(return_value=handler)
        details = _make_call_details("/svc/Err")

        with patch("pykit_server.interceptors.grpc.unary_unary_rpc_method_handler") as mock_wrap:
            mock_wrap.side_effect = lambda fn, **kw: MagicMock(unary_unary=fn)
            wrapped = await interceptor.intercept_service(continuation, details)

        ctx = AsyncMock()
        with pytest.raises(RuntimeError, match="fail"):
            await wrapped.unary_unary(object(), ctx)

        collector.observe_request.assert_called_once()
        args = collector.observe_request.call_args[0]
        assert args[0] == "/svc/Err"
        assert args[1] == "ERROR"
        assert isinstance(args[2], float)

    @pytest.mark.asyncio
    async def test_passes_deserializer_and_serializer(self) -> None:
        deser = object()
        ser = object()
        handler = _make_handler(
            unary_unary=AsyncMock(return_value="ok"),
            request_deserializer=deser,
            response_serializer=ser,
        )
        collector = MagicMock()
        interceptor = MetricsInterceptor(collector=collector)
        continuation = AsyncMock(return_value=handler)
        details = _make_call_details()

        with patch("pykit_server.interceptors.grpc.unary_unary_rpc_method_handler") as mock_wrap:
            mock_wrap.return_value = MagicMock()
            await interceptor.intercept_service(continuation, details)

        _, kwargs = mock_wrap.call_args
        assert kwargs["request_deserializer"] is deser
        assert kwargs["response_serializer"] is ser

