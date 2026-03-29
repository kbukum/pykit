"""gRPC server interceptors — logging, metrics, and error handling."""

from __future__ import annotations

import time
from typing import Any

import grpc
from grpc import aio

import pykit_logging as log
from pykit_errors import AppError


class LoggingInterceptor(aio.ServerInterceptor):
    """Logs every gRPC request with method, duration, and status."""

    def __init__(self) -> None:
        self.logger = log.get_logger("pykit.interceptor.logging")

    async def intercept_service(
        self,
        continuation: Any,
        handler_call_details: grpc.HandlerCallDetails,
    ) -> Any:
        method = handler_call_details.method
        start = time.perf_counter()
        self.logger.info("gRPC request started", method=method)

        handler = await continuation(handler_call_details)
        if handler is None:
            return handler

        # Wrap unary-unary handlers to capture response/errors
        if handler.unary_unary:
            original = handler.unary_unary

            async def wrapped_unary_unary(request: Any, context: grpc.aio.ServicerContext[Any, Any]) -> Any:
                try:
                    response = await original(request, context)
                    elapsed = time.perf_counter() - start
                    self.logger.info(
                        "gRPC request completed",
                        method=method,
                        duration_ms=round(elapsed * 1000, 2),
                        status="OK",
                    )
                    return response
                except Exception as exc:
                    elapsed = time.perf_counter() - start
                    self.logger.error(
                        "gRPC request failed",
                        method=method,
                        duration_ms=round(elapsed * 1000, 2),
                        error=str(exc),
                    )
                    raise

            return grpc.unary_unary_rpc_method_handler(
                wrapped_unary_unary,
                request_deserializer=handler.request_deserializer,
                response_serializer=handler.response_serializer,
            )

        return handler


class ErrorHandlingInterceptor(aio.ServerInterceptor):
    """Catches AppError exceptions and translates them to proper gRPC status codes."""

    def __init__(self) -> None:
        self.logger = log.get_logger("pykit.interceptor.error")

    async def intercept_service(
        self,
        continuation: Any,
        handler_call_details: grpc.HandlerCallDetails,
    ) -> Any:
        handler = await continuation(handler_call_details)
        if handler is None or not handler.unary_unary:
            return handler

        original = handler.unary_unary

        async def wrapped(request: Any, context: grpc.aio.ServicerContext[Any, Any]) -> Any:
            try:
                return await original(request, context)
            except AppError as exc:
                await context.abort(exc.grpc_status, str(exc))
            except Exception as exc:
                self.logger.exception("Unhandled error in gRPC handler", error=str(exc))
                await context.abort(grpc.StatusCode.INTERNAL, "Internal server error")

        return grpc.unary_unary_rpc_method_handler(
            wrapped,
            request_deserializer=handler.request_deserializer,
            response_serializer=handler.response_serializer,
        )


class MetricsInterceptor(aio.ServerInterceptor):
    """Records Prometheus metrics for gRPC calls."""

    def __init__(self, collector: Any = None) -> None:
        self._collector: Any = collector

    async def intercept_service(
        self,
        continuation: Any,
        handler_call_details: grpc.HandlerCallDetails,
    ) -> Any:
        handler = await continuation(handler_call_details)
        if handler is None or not handler.unary_unary or self._collector is None:
            return handler

        original = handler.unary_unary
        method = handler_call_details.method

        async def wrapped(request: Any, context: grpc.aio.ServicerContext[Any, Any]) -> Any:
            start = time.perf_counter()
            try:
                response = await original(request, context)
                elapsed = time.perf_counter() - start
                self._collector.observe_request(method, "OK", elapsed)
                return response
            except Exception:
                elapsed = time.perf_counter() - start
                self._collector.observe_request(method, "ERROR", elapsed)
                raise

        return grpc.unary_unary_rpc_method_handler(
            wrapped,
            request_deserializer=handler.request_deserializer,
            response_serializer=handler.response_serializer,
        )
