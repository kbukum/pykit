"""Tenant context helpers and gRPC tenant interception."""

from __future__ import annotations

import contextvars
from dataclasses import dataclass, field
from typing import Any

import grpc

_tenant_context: contextvars.ContextVar[str | None] = contextvars.ContextVar("tenant_id", default=None)


@dataclass(frozen=True)
class GrpcTenantConfig:
    """Configuration for gRPC tenant extraction."""

    metadata_key: str = "x-tenant-id"
    required: bool = False
    fallback: str | None = None
    skip_methods: frozenset[str] = field(default_factory=frozenset)


TenantConfig = GrpcTenantConfig


def set_tenant(tenant_id: str) -> contextvars.Token[str | None]:
    """Set the current tenant ID in context."""
    return _tenant_context.set(tenant_id)


def get_tenant() -> str | None:
    """Get the current tenant ID from context."""
    return _tenant_context.get()


def require_tenant() -> str:
    """Get the current tenant ID, raising if it is absent."""
    tenant_id = get_tenant()
    if tenant_id is None:
        msg = "No tenant ID set in current context"
        raise RuntimeError(msg)
    return tenant_id


class TenantInterceptor(grpc.aio.ServerInterceptor):  # type: ignore[misc]
    """gRPC server interceptor that extracts tenant ID from request metadata."""

    def __init__(self, config: GrpcTenantConfig | None = None) -> None:
        self.config = config or GrpcTenantConfig()

    async def intercept_service(
        self,
        continuation: Any,
        handler_call_details: grpc.HandlerCallDetails,
    ) -> Any:
        if handler_call_details.method in self.config.skip_methods:
            return await continuation(handler_call_details)

        metadata: list[tuple[str, str]] | tuple[tuple[str, str | bytes], ...] | None = (
            handler_call_details.invocation_metadata
        )
        tenant_id: str | None = None
        for key, value in metadata or []:
            if isinstance(key, str) and key.lower() == self.config.metadata_key.lower():
                tenant_id = value.decode("utf-8") if isinstance(value, bytes) else str(value)
                break

        if not tenant_id:
            if self.config.required:
                return _make_error_handler(grpc.StatusCode.UNAUTHENTICATED, "tenant ID required")
            tenant_id = self.config.fallback

        handler = await continuation(handler_call_details)
        if handler is None or not handler.unary_unary or tenant_id is None:
            return handler

        original = handler.unary_unary

        async def wrapped_unary_unary(request: Any, context: grpc.aio.ServicerContext[Any, Any]) -> Any:
            token = set_tenant(tenant_id)
            try:
                return await original(request, context)
            finally:
                _tenant_context.reset(token)

        return grpc.unary_unary_rpc_method_handler(
            wrapped_unary_unary,
            request_deserializer=handler.request_deserializer,
            response_serializer=handler.response_serializer,
        )


def _make_error_handler(status_code: grpc.StatusCode, details: str) -> Any:
    """Create a handler that aborts the request with a tenant error."""

    async def error_handler(request: Any, context: grpc.aio.ServicerContext[Any, Any]) -> Any:
        del request
        await context.abort(status_code, details)

    return grpc.unary_unary_rpc_method_handler(
        error_handler,
        request_deserializer=lambda value: value,
        response_serializer=lambda value: value,
    )
