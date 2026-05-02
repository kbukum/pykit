"""pykit — Python Infrastructure Library.

Convenience facade that re-exports the public API of every pykit sub-package.
Individual packages can also be imported directly, e.g. ``import pykit_errors``.

Submodules are loaded lazily on first access to keep import time low.
"""

from __future__ import annotations

__version__ = "0.1.0"

# ---------------------------------------------------------------------------
# Lazy submodule access
# ---------------------------------------------------------------------------
# Instead of importing everything eagerly (which would pull in heavy deps
# like OpenTelemetry, httpx, etc.), we expose each sub-package as an
# attribute of this module.  ``pykit.errors`` is equivalent to
# ``import pykit_errors``.

_SUBPACKAGES: dict[str, str] = {
    "errors": "pykit_errors",
    "config": "pykit_config",
    "logging": "pykit_logging",
    "validation": "pykit_validation",
    "encryption": "pykit_encryption",
    "util": "pykit_util",
    "version": "pykit_version",
    "media": "pykit_media",
    "provider": "pykit_provider",
    "component": "pykit_component",
    "resilience": "pykit_resilience",
    "di": "pykit_di",
    "bootstrap": "pykit_bootstrap",
    "observability": "pykit_observability",
    "security": "pykit_security",
    "database": "pykit_database",
    "cache": "pykit_cache",
    "storage": "pykit_storage",
    "kafka": "pykit_messaging",
    "httpclient": "pykit_httpclient",
    "server": "pykit_server",
    "grpc": "pykit_grpc",
    "auth": "pykit_auth",
    "authz": "pykit_authz",
    "pipeline": "pykit_pipeline",
    "dag": "pykit_dag",
    "worker": "pykit_worker",
    "sse": "pykit_sse",
    "stateful": "pykit_stateful",
    "process": "pykit_process",
    "workload": "pykit_workload",
    "llm": "pykit_llm",
    "inference": "pykit_inference",
    "dataset": "pykit_dataset",
    "bench": "pykit_bench",
    "testutil": "pykit_testutil",
    "discovery": "pykit_discovery",
}


def __getattr__(name: str) -> object:
    if name in _SUBPACKAGES:
        import importlib

        mod = importlib.import_module(_SUBPACKAGES[name])
        globals()[name] = mod
        return mod
    raise AttributeError(f"module 'pykit' has no attribute {name!r}")


def __dir__() -> list[str]:
    return [*_SUBPACKAGES, "__version__"]
