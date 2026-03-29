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

    async def deploy(self, req: DeployRequest) -> DeployResult: ...
    async def stop(self, id: str) -> None: ...
    async def remove(self, id: str) -> None: ...
    async def restart(self, id: str) -> None: ...
    async def status(self, id: str) -> WorkloadStatusInfo: ...
    async def wait(self, id: str) -> WaitResult: ...
    async def logs(self, id: str, opts: LogOptions | None = None) -> list[str]: ...
    async def list(self, filter: ListFilter | None = None) -> list[WorkloadInfo]: ...
    async def health_check(self) -> None: ...


@runtime_checkable
class ExecProvider(Protocol):
    """Optional exec capability for workload providers."""

    async def exec(self, id: str, cmd: list[str]) -> ExecResult: ...


@runtime_checkable
class StatsProvider(Protocol):
    """Optional stats capability for workload providers."""

    async def stats(self, id: str) -> WorkloadStats: ...
