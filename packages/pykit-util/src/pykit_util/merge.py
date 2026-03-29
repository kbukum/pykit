"""Deep-merge utilities — pure Python, zero dependencies."""

from __future__ import annotations

from typing import Any


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *override* into *base* (override wins).

    Returns a **new** dict — neither input is mutated.
    """
    result = dict(base)
    for key, over_val in override.items():
        base_val = result.get(key)
        if isinstance(base_val, dict) and isinstance(over_val, dict):
            result[key] = deep_merge(base_val, over_val)
        else:
            result[key] = over_val
    return result
