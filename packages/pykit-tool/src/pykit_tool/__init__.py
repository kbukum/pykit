"""pykit-tool — Tool definition, auto-wiring, and registry.

Provides a type-safe framework for defining tools that can be used in
agentic systems, LLM function calling, or MCP servers.

Usage::

    from pykit_tool import tool, Registry, Context

    @tool(description="Search the web")
    async def search(ctx: Context, query: str, max_results: int = 10) -> list[str]:
        return [f"Result for {query}"]

    registry = Registry()
    registry.register(search)
    result = await registry.call("search", Context(), {"query": "hello"})
"""

from pykit_tool.callable import Callable
from pykit_tool.context import Context
from pykit_tool.decorator import tool
from pykit_tool.definition import Annotations, Definition
from pykit_tool.middleware import (
    Middleware,
    chain,
    with_logging,
    with_result_limit,
    with_timeout,
    with_validation,
)
from pykit_tool.middleware_retry_metrics import (
    InMemoryMetrics,
    MetricsCollector,
    RetryConfig,
    with_metrics,
    with_retry,
)
from pykit_tool.registry import Registry
from pykit_tool.result import Result, error_result, json_result, text_result
from pykit_tool.tool import Tool

__all__ = [
    "Annotations",
    "Callable",
    "Context",
    "Definition",
    "InMemoryMetrics",
    "MetricsCollector",
    "Middleware",
    "Registry",
    "Result",
    "RetryConfig",
    "Tool",
    "chain",
    "error_result",
    "json_result",
    "text_result",
    "tool",
    "with_logging",
    "with_metrics",
    "with_result_limit",
    "with_retry",
    "with_timeout",
    "with_validation",
]
