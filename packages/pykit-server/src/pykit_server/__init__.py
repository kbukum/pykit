"""pykit_server — gRPC server bootstrap, health, interceptors, and HTTP middleware."""

from __future__ import annotations

from pykit_server.base import BaseServer
from pykit_server.health import HealthRegistry
from pykit_server.interceptors import ErrorHandlingInterceptor, LoggingInterceptor, MetricsInterceptor
from pykit_server.middleware import (
    PrometheusMiddleware,
    RateLimitConfig,
    RateLimiter,
    RateLimitMiddleware,
    TenantMiddleware,
    TracingMiddleware,
    ip_based_key,
    user_based_key,
)
from pykit_server.middleware import (
    TenantConfig as HttpTenantConfig,
)
from pykit_server.tenant import (
    GrpcTenantConfig,
    TenantConfig,
    TenantInterceptor,
    get_tenant,
    require_tenant,
    set_tenant,
)

__all__ = [
    "BaseServer",
    "ErrorHandlingInterceptor",
    "GrpcTenantConfig",
    "HealthRegistry",
    "HttpTenantConfig",
    "LoggingInterceptor",
    "MetricsInterceptor",
    "PrometheusMiddleware",
    "RateLimitConfig",
    "RateLimitMiddleware",
    "RateLimiter",
    "TenantConfig",
    "TenantInterceptor",
    "TenantMiddleware",
    "TracingMiddleware",
    "get_tenant",
    "ip_based_key",
    "require_tenant",
    "set_tenant",
    "user_based_key",
]
