from __future__ import annotations


def test_local_retry_metrics_middleware_removed() -> None:
    import pykit_tool.middleware_retry_metrics as removed

    assert removed.__doc__ is not None
