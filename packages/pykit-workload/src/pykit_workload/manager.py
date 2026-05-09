"""pykit_workload.manager — Manager protocol and optional capability protocols."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pykit_workload.models import (
    DeployRequest,
    DeployResult,
    ExecResult,
    ListFilter,
    LogOptions,
    WaitResult,
    WorkloadInfo,
    WorkloadStats,
    WorkloadStatusInfo,
)


@runtime_checkable
class Manager(Protocol):
    """Core workload manager protocol."""

    async def deploy(self, req: DeployRequest) -> DeployResult:
        """Deploy a workload from the supplied request."""

    async def stop(self, id: str) -> None:
        """Stop the workload identified by ``id``."""

    async def remove(self, id: str) -> None:
        """Remove the workload identified by ``id``."""

    async def restart(self, id: str) -> None:
        """Restart the workload identified by ``id``."""

    async def status(self, id: str) -> WorkloadStatusInfo:
        """Return status details for the workload identified by ``id``."""

    async def wait(self, id: str) -> WaitResult:
        """Wait for the workload identified by ``id`` to reach a terminal state."""

    async def logs(self, id: str, opts: LogOptions | None = None) -> list[str]:
        """Return log lines for the workload identified by ``id``."""

    async def list(self, filter: ListFilter | None = None) -> list[WorkloadInfo]:
        """List workloads that match the optional filter."""

    async def health_check(self) -> None:
        """Validate that the manager backend is reachable and healthy."""


@runtime_checkable
class ExecProvider(Protocol):
    """Optional exec capability for workload providers."""

    async def exec(self, id: str, cmd: list[str]) -> ExecResult:
        """Run a command inside the workload identified by ``id``."""


@runtime_checkable
class StatsProvider(Protocol):
    """Optional stats capability for workload providers."""

    async def stats(self, id: str) -> WorkloadStats:
        """Return resource statistics for the workload identified by ``id``."""
