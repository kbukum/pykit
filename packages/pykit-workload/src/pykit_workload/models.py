"""pykit_workload.models — Data models for workload management."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class WorkloadStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    COMPLETED = "completed"
    ERROR = "error"
    RESTARTING = "restarting"
    UNKNOWN = "unknown"
    NOT_FOUND = "not_found"


class ProviderType(StrEnum):
    DOCKER = "docker"
    KUBERNETES = "kubernetes"


@dataclass
class ResourceConfig:
    cpu_limit: str = ""
    cpu_request: str = ""
    memory_limit: str = ""
    memory_request: str = ""


@dataclass
class NetworkConfig:
    mode: str = ""
    dns: list[str] = field(default_factory=list)
    hosts: dict[str, str] = field(default_factory=dict)


@dataclass
class PortMapping:
    host: int = 0
    container: int = 0
    protocol: str = "tcp"


@dataclass
class VolumeMount:
    source: str = ""
    target: str = ""
    read_only: bool = False
    type: str = "bind"


@dataclass
class DeployRequest:
    name: str
    image: str
    command: list[str] = field(default_factory=list)
    args: list[str] = field(default_factory=list)
    environment: dict[str, str] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    work_dir: str = ""
    resources: ResourceConfig | None = None
    network: NetworkConfig | None = None
    volumes: list[VolumeMount] = field(default_factory=list)
    ports: list[PortMapping] = field(default_factory=list)
    restart_policy: str = "no"
    auto_remove: bool = False
    replicas: int = 1
    timeout_seconds: float = 0
    namespace: str = ""
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class DeployResult:
    id: str
    name: str
    status: str


@dataclass
class WaitResult:
    status_code: int
    error: str = ""


@dataclass
class WorkloadInfo:
    id: str
    name: str
    image: str
    status: str
    labels: dict[str, str] = field(default_factory=dict)
    created: datetime | None = None
    namespace: str = ""


@dataclass
class WorkloadStatusInfo:
    id: str
    name: str
    image: str
    status: str
    running: bool = False
    healthy: bool = False
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    exit_code: int = 0
    message: str = ""
    restarts: int = 0


@dataclass
class ExecResult:
    exit_code: int
    stdout: str = ""
    stderr: str = ""


@dataclass
class WorkloadStats:
    cpu_percent: float = 0.0
    memory_usage: int = 0
    memory_limit: int = 0
    network_rx_bytes: int = 0
    network_tx_bytes: int = 0
    pids: int = 0


@dataclass
class WorkloadEvent:
    id: str
    name: str
    event: str
    timestamp: datetime | None = None
    message: str = ""


@dataclass
class LogOptions:
    tail: int = 0
    since_seconds: float = 0
    follow: bool = False


@dataclass
class ListFilter:
    labels: dict[str, str] = field(default_factory=dict)
    name: str = ""
    status: str = ""
    namespace: str = ""
