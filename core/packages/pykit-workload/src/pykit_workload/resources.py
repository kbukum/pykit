"""pykit_workload.resources — Resource parsing utilities (ported from gokit/workload)."""

from __future__ import annotations

_MEMORY_SUFFIXES: list[tuple[str, int]] = [
    ("ti", 1024**4),
    ("gi", 1024**3),
    ("mi", 1024**2),
    ("ki", 1024),
    ("t", 1024**4),
    ("g", 1024**3),
    ("m", 1024**2),
    ("k", 1024),
]


def parse_memory(s: str) -> int:
    """Parse a human-readable memory string to bytes.

    Supported suffixes: k/ki, m/mi, g/gi, t/ti (1024-based).
    Without suffix, the value is treated as bytes.
    """
    s = s.strip().lower()
    if not s:
        raise ValueError("workload: empty memory string")

    multiplier = 1
    for suffix, mult in _MEMORY_SUFFIXES:
        if s.endswith(suffix):
            multiplier = mult
            s = s[: -len(suffix)]
            break

    try:
        val = int(s)
    except ValueError:
        raise ValueError(f"workload: parse memory {s!r}: invalid integer") from None

    if val < 0:
        raise ValueError(f"workload: memory must be non-negative: {val}")

    return val * multiplier


def parse_cpu(s: str) -> int:
    """Parse a human-readable CPU string to nanocores.

    Supported formats: "500m" (millicores), "0.5" or "1" (cores).
    """
    s = s.strip().lower()
    if not s:
        raise ValueError("workload: empty CPU string")

    if s.endswith("m"):
        try:
            val = float(s[:-1])
        except ValueError:
            raise ValueError(f"workload: parse CPU {s!r}: invalid number") from None
        return int(val * 1e6)

    try:
        val = float(s)
    except ValueError:
        raise ValueError(f"workload: parse CPU {s!r}: invalid number") from None
    return int(val * 1e9)


def format_memory(bytes_val: int) -> str:
    """Format bytes as a human-readable memory string."""
    if bytes_val >= 1024**3:
        return f"{bytes_val // (1024**3)}g"
    if bytes_val >= 1024**2:
        return f"{bytes_val // (1024**2)}m"
    if bytes_val >= 1024:
        return f"{bytes_val // 1024}k"
    return str(bytes_val)


def format_cpu(nanocores: int) -> str:
    """Format nanocores as a human-readable CPU string."""
    if nanocores % int(1e9) == 0:
        return str(nanocores // int(1e9))
    if nanocores % int(1e6) == 0:
        return f"{nanocores // int(1e6)}m"
    return f"{nanocores / 1e9:.3f}"
