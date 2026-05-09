"""pykit-tool — Tool definition, executable envelope, and registry."""

from pykit_tool.callable import Callable
from pykit_tool.context import Context
from pykit_tool.decorator import tool
from pykit_tool.definition import (
    Annotations,
    DataClassification,
    Definition,
    Envelope,
    ExecutionHint,
    FilesystemMode,
    FilesystemRule,
    NetworkPolicy,
    NetworkRule,
    Safety,
    SensitiveMatcher,
    SensitivePredicate,
    SubprocessRule,
)
from pykit_tool.middleware import Middleware, chain
from pykit_tool.registry import (
    BatchOptions,
    HumanApprovalDeniedError,
    Registry,
    SensitivityDeniedError,
)
from pykit_tool.result import Result, error_result, json_result, text_result
from pykit_tool.sensitivity import (
    Decision,
    DenyHumanApproval,
    DenyOnSensitiveEvaluator,
    HumanApproval,
    RequireApprovalEvaluator,
    SensitivityEvaluator,
    ToolCall,
    evaluate_envelope,
)
from pykit_tool.tool import Tool

__all__ = [
    "Annotations",
    "BatchOptions",
    "Callable",
    "Context",
    "DataClassification",
    "Decision",
    "Definition",
    "DenyHumanApproval",
    "DenyOnSensitiveEvaluator",
    "Envelope",
    "ExecutionHint",
    "FilesystemMode",
    "FilesystemRule",
    "HumanApproval",
    "HumanApprovalDeniedError",
    "Middleware",
    "NetworkPolicy",
    "NetworkRule",
    "Registry",
    "RequireApprovalEvaluator",
    "Result",
    "Safety",
    "SensitiveMatcher",
    "SensitivePredicate",
    "SensitivityDeniedError",
    "SensitivityEvaluator",
    "SubprocessRule",
    "Tool",
    "ToolCall",
    "chain",
    "error_result",
    "evaluate_envelope",
    "json_result",
    "text_result",
    "tool",
]
