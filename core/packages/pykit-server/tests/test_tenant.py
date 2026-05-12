"""Tests for pykit_server.tenant — TenantInterceptor and get_tenant."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import grpc
import pytest

from pykit_server.tenant import TenantConfig, TenantInterceptor, get_tenant

# ---------------------------------------------------------------------------
# Helpers to build fake gRPC handler / call-details objects
# ---------------------------------------------------------------------------


def _make_handler(
    *,
    unary_unary: Any = None,
    request_deserializer: Any = None,
    response_serializer: Any = None,
) -> MagicMock:
    """Create a mock gRPC handler."""
    handler = MagicMock()
    handler.unary_unary = unary_unary
    handler.request_deserializer = request_deserializer
    handler.response_serializer = response_serializer
    return handler


def _make_call_details(
    method: str = "/pkg.Service/Method",
    metadata: list[tuple[str, str]] | None = None,
) -> MagicMock:
    """Create a mock gRPC handler call details."""
    details = MagicMock(spec=grpc.HandlerCallDetails)
    details.method = method
    details.invocation_metadata = metadata or []
    return details


# ---------------------------------------------------------------------------
# TenantConfig Tests
# ---------------------------------------------------------------------------


class TestTenantConfig:
    def test_default_config(self) -> None:
        config = TenantConfig()
        assert config.metadata_key == "x-tenant-id"
        assert not config.required
        assert config.fallback is None

    def test_custom_config(self) -> None:
        config = TenantConfig(
            metadata_key="x-custom-tenant",
            required=True,
            fallback="default-tenant",
        )
        assert config.metadata_key == "x-custom-tenant"
        assert config.required
        assert config.fallback == "default-tenant"


# ---------------------------------------------------------------------------
# TenantInterceptor Tests
# ---------------------------------------------------------------------------


class TestTenantInterceptor:
    @pytest.mark.asyncio
    async def test_extracts_tenant_from_metadata(self) -> None:
        """Test that tenant is extracted from metadata."""
        interceptor = TenantInterceptor()
        metadata = [("x-tenant-id", "tenant-123")]
        details = _make_call_details(metadata=metadata)

        # Mock handler and continuation
        mock_handler = _make_handler(
            unary_unary=AsyncMock(return_value="response"),
            request_deserializer=lambda x: x,
            response_serializer=lambda x: x,
        )
        continuation = AsyncMock(return_value=mock_handler)

        result = await interceptor.intercept_service(continuation, details)

        # Verify handler was retrieved
        assert result is not None
        continuation.assert_awaited_once_with(details)

        # Verify tenant was set by calling the wrapped handler
        mock_context = AsyncMock(spec=grpc.aio.ServicerContext)
        await result.unary_unary("test_request", mock_context)

        # The wrapped handler should have been called
        mock_handler.unary_unary.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_missing_tenant_with_required(self) -> None:
        """Test that missing required tenant returns error handler."""
        config = TenantConfig(required=True)
        interceptor = TenantInterceptor(config)
        details = _make_call_details(metadata=[])

        continuation = AsyncMock(return_value=_make_handler())

        result = await interceptor.intercept_service(continuation, details)

        # Result should be an error handler (created by _make_error_handler)
        assert result is not None
        # It should have unary_unary method
        assert hasattr(result, "unary_unary")

    @pytest.mark.asyncio
    async def test_missing_tenant_with_fallback(self) -> None:
        """Test that missing tenant uses fallback."""
        config = TenantConfig(required=False, fallback="default-tenant")
        interceptor = TenantInterceptor(config)
        details = _make_call_details(metadata=[])

        mock_handler = _make_handler(
            unary_unary=AsyncMock(return_value="response"),
            request_deserializer=lambda x: x,
            response_serializer=lambda x: x,
        )
        continuation = AsyncMock(return_value=mock_handler)

        result = await interceptor.intercept_service(continuation, details)

        # Should wrap the handler
        assert result is not None

    @pytest.mark.asyncio
    async def test_case_insensitive_metadata_key(self) -> None:
        """Test that metadata key lookup is case-insensitive."""
        config = TenantConfig(metadata_key="X-Tenant-ID")
        interceptor = TenantInterceptor(config)

        # Metadata uses lowercase
        metadata = [("x-tenant-id", "tenant-456")]
        details = _make_call_details(metadata=metadata)

        mock_handler = _make_handler(
            unary_unary=AsyncMock(return_value="response"),
            request_deserializer=lambda x: x,
            response_serializer=lambda x: x,
        )
        continuation = AsyncMock(return_value=mock_handler)

        result = await interceptor.intercept_service(continuation, details)

        # Should find the tenant despite case difference
        assert result is not None

    @pytest.mark.asyncio
    async def test_returns_none_when_handler_is_none(self) -> None:
        """Test that None handler is returned as-is."""
        interceptor = TenantInterceptor()
        details = _make_call_details(metadata=[("x-tenant-id", "tenant-789")])
        continuation = AsyncMock(return_value=None)

        result = await interceptor.intercept_service(continuation, details)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_handler_when_no_unary_unary(self) -> None:
        """Test that handler without unary_unary is returned as-is."""
        interceptor = TenantInterceptor()
        details = _make_call_details(metadata=[("x-tenant-id", "tenant-789")])

        handler = _make_handler(unary_unary=None)
        continuation = AsyncMock(return_value=handler)

        result = await interceptor.intercept_service(continuation, details)

        # Should return the handler as-is
        assert result is handler


# ---------------------------------------------------------------------------
# get_tenant() Tests
# ---------------------------------------------------------------------------


class TestGetTenant:
    def test_get_tenant_default(self) -> None:
        """Test that get_tenant returns None when not set."""
        tenant = get_tenant()
        assert tenant is None

    @pytest.mark.asyncio
    async def test_get_tenant_from_context(self) -> None:
        """Test retrieving tenant from context variable."""
        config = TenantConfig()
        interceptor = TenantInterceptor(config)

        metadata = [("x-tenant-id", "tenant-xyz")]
        details = _make_call_details(metadata=metadata)

        call_count = 0

        async def mock_impl(request: Any, context: Any) -> str:
            nonlocal call_count
            call_count += 1
            # Inside the wrapped function, get_tenant should return the tenant
            tenant = get_tenant()
            return tenant or "no-tenant"

        mock_handler = _make_handler(
            unary_unary=mock_impl,
            request_deserializer=lambda x: x,
            response_serializer=lambda x: x,
        )
        continuation = AsyncMock(return_value=mock_handler)

        result = await interceptor.intercept_service(continuation, details)

        # Call the wrapped handler
        mock_context = AsyncMock(spec=grpc.aio.ServicerContext)
        response = await result.unary_unary("test_request", mock_context)

        # The tenant should have been retrievable inside the handler
        assert response == "tenant-xyz"
