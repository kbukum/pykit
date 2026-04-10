"""Tool definition types — MCP-aligned metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Annotations:
    """Optional hints about tool behavior (MCP-aligned).

    Attributes:
        title: Human-readable title.
        read_only_hint: True if the tool only reads data.
        destructive_hint: True if the tool may cause irreversible changes.
        idempotent_hint: True if repeated calls produce the same result.
        open_world_hint: True if the tool interacts with external systems.
        category: Grouping category for UI.
        tags: Freeform tags for filtering.
        execution_hint: How the frontend should handle the tool result.
            ``"ui"`` — tool only validates/extracts params; frontend drives the action.
            ``"backend"`` — tool executes a real operation; result is authoritative.
            ``"hybrid"`` — tool executes backend AND frontend should refresh/navigate.
            Empty string defaults to ``"backend"`` for backward compatibility.
    """

    title: str = ""
    read_only_hint: bool | None = None
    destructive_hint: bool | None = None
    idempotent_hint: bool | None = None
    open_world_hint: bool | None = None
    category: str = ""
    tags: list[str] = field(default_factory=list)
    execution_hint: str = ""


@dataclass(frozen=True)
class Definition:
    """Describes a tool — MCP-aligned metadata.

    Attributes:
        name: Unique tool identifier (e.g. ``"search_web"``).
        description: Human-readable description of what the tool does.
        input_schema: JSON Schema for the tool's input parameters.
        output_schema: Optional JSON Schema for the tool's output.
        annotations: Optional behavioral hints.
        read_only: True if the tool only reads data (no side effects).
        destructive: True if the tool may cause irreversible changes.
        timeout: Default timeout in seconds (0 = no default).
        max_result_size: Maximum result size in bytes (0 = unlimited).
    """

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] | None = None
    annotations: Annotations | None = None
    read_only: bool = False
    destructive: bool = False
    timeout: float = 0.0
    max_result_size: int = 0
