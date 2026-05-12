"""Tests for pykit_workload."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pykit_workload import (
    DeployRequest,
    DeployResult,
    ExecProvider,
    ExecResult,
    ListFilter,
    LogOptions,
    Manager,
    NetworkConfig,
    PortMapping,
    ProviderType,
    ResourceConfig,
    StatsProvider,
    VolumeMount,
    WaitResult,
    WorkloadConfig,
    WorkloadEvent,
    WorkloadInfo,
    WorkloadStats,
    WorkloadStatus,
    WorkloadStatusInfo,
    create_manager,
    format_cpu,
    format_memory,
    parse_cpu,
    parse_memory,
    register_factory,
)
from pykit_workload.config import _factories

# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestModels:
    def test_workload_status_values(self) -> None:
        assert WorkloadStatus.CREATED == "created"
        assert WorkloadStatus.RUNNING == "running"
        assert WorkloadStatus.ERROR == "error"
        assert WorkloadStatus.NOT_FOUND == "not_found"

    def test_provider_type_values(self) -> None:
        assert ProviderType.DOCKER == "docker"
        assert ProviderType.KUBERNETES == "kubernetes"

    def test_deploy_request_defaults(self) -> None:
        req = DeployRequest(name="web", image="nginx:latest")
        assert req.name == "web"
        assert req.image == "nginx:latest"
        assert req.command == []
        assert req.args == []
        assert req.environment == {}
        assert req.labels == {}
        assert req.work_dir == ""
        assert req.resources is None
        assert req.network is None
        assert req.volumes == []
        assert req.ports == []
        assert req.restart_policy == "no"
        assert req.auto_remove is False
        assert req.replicas == 1
        assert req.timeout_seconds == 0
        assert req.namespace == ""
        assert req.metadata == {}

    def test_deploy_request_with_resources(self) -> None:
        rc = ResourceConfig(cpu_limit="1", memory_limit="512m")
        req = DeployRequest(name="api", image="app:v1", resources=rc)
        assert req.resources is not None
        assert req.resources.cpu_limit == "1"

    def test_deploy_result(self) -> None:
        r = DeployResult(id="abc", name="web", status="running")
        assert r.id == "abc"
        assert r.status == "running"

    def test_wait_result_defaults(self) -> None:
        r = WaitResult(status_code=0)
        assert r.error == ""

    def test_workload_info_defaults(self) -> None:
        info = WorkloadInfo(id="1", name="web", image="nginx", status="running")
        assert info.labels == {}
        assert info.created is None
        assert info.namespace == ""

    def test_workload_info_with_datetime(self) -> None:
        now = datetime.now(tz=UTC)
        info = WorkloadInfo(id="1", name="web", image="nginx", status="running", created=now)
        assert info.created == now

    def test_workload_status_info_defaults(self) -> None:
        s = WorkloadStatusInfo(id="1", name="web", image="nginx", status="running")
        assert s.running is False
        assert s.healthy is False
        assert s.started_at is None
        assert s.stopped_at is None
        assert s.exit_code == 0
        assert s.message == ""
        assert s.restarts == 0

    def test_exec_result(self) -> None:
        r = ExecResult(exit_code=0, stdout="hello\n")
        assert r.stderr == ""

    def test_workload_stats_defaults(self) -> None:
        s = WorkloadStats()
        assert s.cpu_percent == 0.0
        assert s.memory_usage == 0
        assert s.pids == 0

    def test_workload_event(self) -> None:
        e = WorkloadEvent(id="1", name="web", event="start")
        assert e.timestamp is None
        assert e.message == ""

    def test_log_options_defaults(self) -> None:
        opts = LogOptions()
        assert opts.tail == 0
        assert opts.since_seconds == 0
        assert opts.follow is False

    def test_list_filter_defaults(self) -> None:
        f = ListFilter()
        assert f.labels == {}
        assert f.name == ""
        assert f.status == ""
        assert f.namespace == ""

    def test_resource_config(self) -> None:
        rc = ResourceConfig(cpu_limit="500m", memory_limit="256mi")
        assert rc.cpu_request == ""
        assert rc.memory_request == ""

    def test_network_config(self) -> None:
        nc = NetworkConfig(mode="bridge", dns=["8.8.8.8"])
        assert nc.hosts == {}

    def test_port_mapping(self) -> None:
        pm = PortMapping(host=8080, container=80)
        assert pm.protocol == "tcp"

    def test_volume_mount(self) -> None:
        vm = VolumeMount(source="/data", target="/mnt/data")
        assert vm.read_only is False
        assert vm.type == "bind"


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


class TestWorkloadConfig:
    def test_defaults(self) -> None:
        cfg = WorkloadConfig()
        assert cfg.provider == "docker"
        assert cfg.enabled is False
        assert cfg.default_labels == {}

    def test_validate_ok(self) -> None:
        cfg = WorkloadConfig(provider="docker")
        cfg.validate()  # should not raise

    def test_validate_empty_provider(self) -> None:
        cfg = WorkloadConfig(provider="")
        with pytest.raises(ValueError, match="provider is required"):
            cfg.validate()


# ---------------------------------------------------------------------------
# Factory tests
# ---------------------------------------------------------------------------


class TestFactory:
    def setup_method(self) -> None:
        _factories.clear()

    def test_register_and_create(self) -> None:
        class FakeManager:
            pass

        def factory(cfg: WorkloadConfig, provider_cfg: object = None) -> FakeManager:
            return FakeManager()

        register_factory("docker", factory)
        mgr = create_manager(WorkloadConfig(provider="docker"))
        assert isinstance(mgr, FakeManager)

    def test_create_unknown_provider(self) -> None:
        with pytest.raises(ValueError, match="unsupported provider"):
            create_manager(WorkloadConfig(provider="unknown"))

    def test_create_validates_config(self) -> None:
        with pytest.raises(ValueError, match="provider is required"):
            create_manager(WorkloadConfig(provider=""))


# ---------------------------------------------------------------------------
# Resource parsing tests
# ---------------------------------------------------------------------------


class TestParseMemory:
    def test_bytes(self) -> None:
        assert parse_memory("1024") == 1024

    def test_kilobytes(self) -> None:
        assert parse_memory("1k") == 1024
        assert parse_memory("1K") == 1024

    def test_kibibytes(self) -> None:
        assert parse_memory("1ki") == 1024
        assert parse_memory("1Ki") == 1024

    def test_megabytes(self) -> None:
        assert parse_memory("512m") == 512 * 1024**2

    def test_mebibytes(self) -> None:
        assert parse_memory("512mi") == 512 * 1024**2

    def test_gigabytes(self) -> None:
        assert parse_memory("2g") == 2 * 1024**3

    def test_gibibytes(self) -> None:
        assert parse_memory("2gi") == 2 * 1024**3

    def test_terabytes(self) -> None:
        assert parse_memory("1t") == 1024**4

    def test_tebibytes(self) -> None:
        assert parse_memory("1ti") == 1024**4

    def test_whitespace(self) -> None:
        assert parse_memory("  512m  ") == 512 * 1024**2

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="empty memory string"):
            parse_memory("")

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid integer"):
            parse_memory("abc")

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            parse_memory("-1m")


class TestParseCPU:
    def test_millicores(self) -> None:
        assert parse_cpu("500m") == 500_000_000

    def test_one_core(self) -> None:
        assert parse_cpu("1") == 1_000_000_000

    def test_fractional_core(self) -> None:
        assert parse_cpu("0.5") == 500_000_000

    def test_two_cores(self) -> None:
        assert parse_cpu("2") == 2_000_000_000

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="empty CPU string"):
            parse_cpu("")

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid number"):
            parse_cpu("abc")

    def test_invalid_millicores_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid number"):
            parse_cpu("xyzm")


class TestFormatMemory:
    def test_gigabytes(self) -> None:
        assert format_memory(2 * 1024**3) == "2g"

    def test_megabytes(self) -> None:
        assert format_memory(512 * 1024**2) == "512m"

    def test_kilobytes(self) -> None:
        assert format_memory(64 * 1024) == "64k"

    def test_bytes(self) -> None:
        assert format_memory(500) == "500"


class TestFormatCPU:
    def test_whole_cores(self) -> None:
        assert format_cpu(1_000_000_000) == "1"
        assert format_cpu(2_000_000_000) == "2"

    def test_millicores(self) -> None:
        assert format_cpu(500_000_000) == "500m"
        assert format_cpu(250_000_000) == "250m"

    def test_fractional(self) -> None:
        assert format_cpu(1_500_000) == "0.002"


# ---------------------------------------------------------------------------
# Protocol tests
# ---------------------------------------------------------------------------


class TestManagerProtocol:
    def test_mock_manager_satisfies_protocol(self) -> None:
        class MockManager:
            async def deploy(self, req: DeployRequest) -> DeployResult:
                return DeployResult(id="1", name=req.name, status="running")

            async def stop(self, id: str) -> None:
                pass

            async def remove(self, id: str) -> None:
                pass

            async def restart(self, id: str) -> None:
                pass

            async def status(self, id: str) -> WorkloadStatusInfo:
                return WorkloadStatusInfo(id=id, name="", image="", status="running")

            async def wait(self, id: str) -> WaitResult:
                return WaitResult(status_code=0)

            async def logs(self, id: str, opts: LogOptions | None = None) -> list[str]:
                return []

            async def list(self, filter: ListFilter | None = None) -> list[WorkloadInfo]:
                return []

            async def health_check(self) -> None:
                pass

        mgr = MockManager()
        assert isinstance(mgr, Manager)

    async def test_mock_manager_deploy(self) -> None:
        class MockManager:
            async def deploy(self, req: DeployRequest) -> DeployResult:
                return DeployResult(id="c1", name=req.name, status="created")

            async def stop(self, id: str) -> None:
                pass

            async def remove(self, id: str) -> None:
                pass

            async def restart(self, id: str) -> None:
                pass

            async def status(self, id: str) -> WorkloadStatusInfo:
                return WorkloadStatusInfo(id=id, name="", image="", status="running")

            async def wait(self, id: str) -> WaitResult:
                return WaitResult(status_code=0)

            async def logs(self, id: str, opts: LogOptions | None = None) -> list[str]:
                return []

            async def list(self, filter: ListFilter | None = None) -> list[WorkloadInfo]:
                return []

            async def health_check(self) -> None:
                pass

        mgr = MockManager()
        result = await mgr.deploy(DeployRequest(name="web", image="nginx"))
        assert result.id == "c1"
        assert result.name == "web"


class TestExecProviderProtocol:
    def test_satisfies_protocol(self) -> None:
        class MockExec:
            async def exec(self, id: str, cmd: list[str]) -> ExecResult:
                return ExecResult(exit_code=0, stdout="ok")

        assert isinstance(MockExec(), ExecProvider)

    async def test_exec_call(self) -> None:
        class MockExec:
            async def exec(self, id: str, cmd: list[str]) -> ExecResult:
                return ExecResult(exit_code=0, stdout=" ".join(cmd))

        result = await MockExec().exec("c1", ["echo", "hello"])
        assert result.stdout == "echo hello"


class TestStatsProviderProtocol:
    def test_satisfies_protocol(self) -> None:
        class MockStats:
            async def stats(self, id: str) -> WorkloadStats:
                return WorkloadStats(cpu_percent=50.0, pids=3)

        assert isinstance(MockStats(), StatsProvider)

    async def test_stats_call(self) -> None:
        class MockStats:
            async def stats(self, id: str) -> WorkloadStats:
                return WorkloadStats(cpu_percent=25.5, memory_usage=1024)

        result = await MockStats().stats("c1")
        assert result.cpu_percent == 25.5
        assert result.memory_usage == 1024
