"""Multi-tenant context extraction for gRPC services."""

from __future__ import annotations

import contextvars
from dataclasses import dataclass
from typing import Any

import grpc

# Context variable to store the current tenant ID
_tenant_context: contextvars.ContextVar[str | None] = contextvars.ContextVar("tenant_id", default=None)


@dataclass
class TenantConfig:
    """Configuration for tenant extraction.

    Attributes:
        metadata_key: gRPC metadata key to read tenant ID from (default: "x-tenant-id").
        required: If True, requests without tenant ID are rejected with UNAUTHENTICATED.
        fallback: Optional default tenant ID when metadata is missing and not required.
    """

    metadata_key: str = "x-tenant-id"
    required: bool = False
    fallback: str | None = None


class TenantInterceptor(grpc.aio.ServerInterceptor):  # type: ignore[misc]  # ServerInterceptor is from untyped grpc library
    """gRPC server interceptor that extracts tenant ID from request metadata.

    The tenant ID is read from the configured metadata key (default: "x-tenant-id").
    If not found and required=True, returns UNAUTHENTICATED status.
    If not found and fallback is set, uses the fallback tenant ID.
    The tenant ID is stored in a context variable for retrieval via get_tenant().

    Example:
        >>> config = TenantConfig(metadata_key="x-tenant-id", required=True)
        >>> interceptor = TenantInterceptor(config)
        >>> # Use in gRPC server:
        >>> server = grpc.aio.server(interceptors=[interceptor])
    """

    def __init__(self, config: TenantConfig | None = None) -> None:
        """Initialize TenantInterceptor.

        Args:
            config: TenantConfig instance. If None, uses default config.
        """
        self.config = config or TenantConfig()

    async def intercept_service(
        self,
        continuation: Any,
        handler_call_details: grpc.HandlerCallDetails,
    ) -> Any:
        """Intercept gRPC service call to extract and store tenant ID.

        Args:
            continuation: Async function to call next interceptor or handler.
            handler_call_details: gRPC handler call details with method and metadata.

        Returns:
            The handler from continuation.

        Raises:
            grpc.RpcError: With UNAUTHENTICATED status if tenant is required but missing.
        """
        # Extract metadata as a list of tuples
        metadata: list[tuple[str, str]] | tuple[tuple[str, str | bytes], ...] | None = (
            handler_call_details.invocation_metadata
        )
        if not metadata:
            metadata = []

        # Find tenant ID in metadata
        tenant_id: str | None = None
        for key, value in metadata:
            if isinstance(key, str) and key.lower() == self.config.metadata_key.lower():
                if isinstance(value, bytes):
                    tenant_id = value.decode("utf-8")
                else:
                    tenant_id = str(value) if value is not None else None
                break

        # Handle missing tenant ID
        if not tenant_id:
            if self.config.required:
                # Return an error handler that will abort with UNAUTHENTICATED
                return _make_error_handler(grpc.StatusCode.UNAUTHENTICATED, "tenant ID required")
            tenant_id = self.config.fallback or ""

        # Continue to the actual handler with tenant ID in context
        handler = await continuation(handler_call_details)

        # If there's no handler or no unary_unary, return as-is
        if handler is None or not handler.unary_unary:
            return handler

        # Wrap the handler to set tenant context
        original = handler.unary_unary

        async def wrapped_unary_unary(request: Any, context: grpc.aio.ServicerContext[Any, Any]) -> Any:
            # Set tenant ID in context var
            token = _tenant_context.set(tenant_id)
            try:
                return await original(request, context)
            finally:
                _tenant_context.reset(token)

        # Return a handler with the wrapped function
        return grpc.unary_unary_rpc_method_handler(
            wrapped_unary_unary,
            request_deserializer=handler.request_deserializer,
            response_serializer=handler.response_serializer,
        )


def get_tenant() -> str | None:
    """Get the current tenant ID from context.

    Returns the tenant ID if set by TenantInterceptor, or None otherwise.

    Returns:
        The current tenant ID, or None if not set.
    """
    return _tenant_context.get()


def _make_error_handler(status_code: grpc.StatusCode, details: str) -> Any:
    """Create a handler that returns an error response."""

    async def error_handler(request: Any, context: grpc.aio.ServicerContext[Any, Any]) -> Any:
        await context.abort(status_code, details)

    # Return a handler-like object
    handler = grpc.unary_unary_rpc_method_handler(
        error_handler,
        request_deserializer=lambda x: x,
        response_serializer=lambda x: x,
    )
    return handler
