"""Extended edge-case tests for pykit_workload."""

from __future__ import annotations

import dataclasses
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
    format_cpu,
    format_memory,
    parse_cpu,
    parse_memory,
)


# ---------------------------------------------------------------------------
# DeployRequest edge cases
# ---------------------------------------------------------------------------


class TestDeployRequestEdgeCases:
    def test_large_environment_map(self) -> None:
        env = {f"VAR_{i}": f"val_{i}" for i in range(200)}
        req = DeployRequest(name="big-env", image="app", environment=env)
        assert len(req.environment) == 200

    def test_serialization_roundtrip(self) -> None:
        rc = ResourceConfig(cpu_limit="500m", memory_limit="256m")
        req = DeployRequest(
            name="web",
            image="nginx:latest",
            command=["/bin/sh"],
            args=["-c", "echo hello"],
            environment={"FOO": "bar"},
            labels={"app": "web"},
            resources=rc,
            volumes=[VolumeMount(source="/data", target="/mnt", read_only=True)],
            ports=[PortMapping(host=8080, container=80)],
            restart_policy="always",
            replicas=3,
        )
        d = dataclasses.asdict(req)
        assert d["name"] == "web"
        assert d["image"] == "nginx:latest"
        assert d["resources"]["cpu_limit"] == "500m"
        assert d["volumes"][0]["read_only"] is True
        assert d["ports"][0]["host"] == 8080
        assert d["replicas"] == 3

    def test_long_command_args(self) -> None:
        args = ["a" * 1000 for _ in range(100)]
        req = DeployRequest(name="long", image="app", args=args)
        assert len(req.args) == 100
        assert len(req.args[0]) == 1000

    def test_metadata_arbitrary_types(self) -> None:
        req = DeployRequest(
            name="meta",
            image="app",
            metadata={"int": 42, "list": [1, 2], "nested": {"a": "b"}},
        )
        assert req.metadata["int"] == 42
        assert req.metadata["list"] == [1, 2]
        assert req.metadata["nested"]["a"] == "b"


# ---------------------------------------------------------------------------
# WorkloadStatus transitions
# ---------------------------------------------------------------------------


class TestWorkloadStatusTransitions:
    def test_all_status_values_unique(self) -> None:
        values = [s.value for s in WorkloadStatus]
        assert len(values) == len(set(values))

    def test_all_statuses_are_strings(self) -> None:
        for s in WorkloadStatus:
            assert isinstance(s, str)
            assert isinstance(s.value, str)

    def test_status_membership(self) -> None:
        assert "running" in [s.value for s in WorkloadStatus]
        assert "stopped" in [s.value for s in WorkloadStatus]
        assert "invalid" not in [s.value for s in WorkloadStatus]

    def test_status_count(self) -> None:
        assert len(WorkloadStatus) == 8


# ---------------------------------------------------------------------------
# WorkloadConfig edge cases
# ---------------------------------------------------------------------------


class TestWorkloadConfigEdgeCases:
    def test_defaults_are_correct(self) -> None:
        cfg = WorkloadConfig()
        assert cfg.provider == "docker"
        assert cfg.enabled is False
        assert cfg.default_labels == {}

    def test_custom_default_labels(self) -> None:
        cfg = WorkloadConfig(default_labels={"team": "platform"})
        assert cfg.default_labels["team"] == "platform"

    def test_validate_whitespace_provider(self) -> None:
        cfg = WorkloadConfig(provider="  ")
        # Non-empty string passes validation (provider=" " is truthy)
        cfg.validate()


# ---------------------------------------------------------------------------
# ResourceConfig edge cases
# ---------------------------------------------------------------------------


class TestResourceConfigEdgeCases:
    def test_all_empty_strings(self) -> None:
        rc = ResourceConfig()
        assert rc.cpu_limit == ""
        assert rc.cpu_request == ""
        assert rc.memory_limit == ""
        assert rc.memory_request == ""

    def test_all_fields_populated(self) -> None:
        rc = ResourceConfig(
            cpu_limit="2", cpu_request="500m", memory_limit="1g", memory_request="256m"
        )
        assert rc.cpu_limit == "2"
        assert rc.memory_request == "256m"


# ---------------------------------------------------------------------------
# NetworkConfig / PortMapping edge cases
# ---------------------------------------------------------------------------


class TestNetworkConfigEdgeCases:
    def test_multiple_dns_servers(self) -> None:
        nc = NetworkConfig(mode="bridge", dns=["8.8.8.8", "1.1.1.1", "8.8.4.4"])
        assert len(nc.dns) == 3

    def test_hosts_mapping(self) -> None:
        nc = NetworkConfig(hosts={"myhost": "10.0.0.1", "db": "10.0.0.2"})
        assert nc.hosts["db"] == "10.0.0.2"


class TestPortMappingEdgeCases:
    def test_udp_protocol(self) -> None:
        pm = PortMapping(host=53, container=53, protocol="udp")
        assert pm.protocol == "udp"

    def test_zero_ports(self) -> None:
        pm = PortMapping()
        assert pm.host == 0
        assert pm.container == 0


# ---------------------------------------------------------------------------
# VolumeMount edge cases
# ---------------------------------------------------------------------------


class TestVolumeMountEdgeCases:
    def test_readonly_flag(self) -> None:
        vm = VolumeMount(source="/secrets", target="/mnt/secrets", read_only=True)
        assert vm.read_only is True

    def test_different_types(self) -> None:
        for vol_type in ("bind", "volume", "configmap", "secret", "pvc"):
            vm = VolumeMount(source="src", target="/tgt", type=vol_type)
            assert vm.type == vol_type


# ---------------------------------------------------------------------------
# WaitResult edge cases
# ---------------------------------------------------------------------------


class TestWaitResultEdgeCases:
    def test_with_error_details(self) -> None:
        r = WaitResult(status_code=137, error="OOMKilled")
        assert r.status_code == 137
        assert r.error == "OOMKilled"

    def test_success(self) -> None:
        r = WaitResult(status_code=0)
        assert r.error == ""

    def test_nonzero_without_error(self) -> None:
        r = WaitResult(status_code=1)
        assert r.status_code == 1
        assert r.error == ""


# ---------------------------------------------------------------------------
# Manager protocol verification
# ---------------------------------------------------------------------------


class TestManagerProtocolExtended:
    def test_incomplete_manager_not_instance(self) -> None:
        class IncompleteManager:
            async def deploy(self, req: DeployRequest) -> DeployResult:
                return DeployResult(id="1", name="", status="")

        # Missing other methods → not a Manager
        assert not isinstance(IncompleteManager(), Manager)

    def test_exec_provider_protocol(self) -> None:
        class MockExec:
            async def exec(self, id: str, cmd: list[str]) -> ExecResult:
                return ExecResult(exit_code=0, stdout="ok")

        assert isinstance(MockExec(), ExecProvider)

    def test_stats_provider_protocol(self) -> None:
        class MockStats:
            async def stats(self, id: str) -> WorkloadStats:
                return WorkloadStats(cpu_percent=10.0)

        assert isinstance(MockStats(), StatsProvider)


# ---------------------------------------------------------------------------
# Resource parsing edge cases
# ---------------------------------------------------------------------------


class TestResourceParsingEdgeCases:
    def test_parse_memory_zero(self) -> None:
        assert parse_memory("0") == 0

    def test_parse_cpu_very_small(self) -> None:
        result = parse_cpu("1m")
        assert result == 1_000_000

    def test_parse_cpu_large(self) -> None:
        result = parse_cpu("64")
        assert result == 64_000_000_000

    def test_format_memory_zero(self) -> None:
        assert format_memory(0) == "0"

    def test_format_cpu_zero(self) -> None:
        assert format_cpu(0) == "0"

    def test_parse_format_memory_roundtrip(self) -> None:
        for val_str in ("1g", "512m", "64k"):
            parsed = parse_memory(val_str)
            formatted = format_memory(parsed)
            assert formatted == val_str

    def test_parse_format_cpu_roundtrip(self) -> None:
        for val_str in ("1", "2", "500m", "250m"):
            parsed = parse_cpu(val_str)
            formatted = format_cpu(parsed)
            assert formatted == val_str

    def test_parse_memory_case_insensitive(self) -> None:
        assert parse_memory("1G") == parse_memory("1g")
        assert parse_memory("1GI") == parse_memory("1gi")
        assert parse_memory("512M") == parse_memory("512m")


# ---------------------------------------------------------------------------
# WorkloadStatusInfo edge cases
# ---------------------------------------------------------------------------


class TestWorkloadStatusInfoEdgeCases:
    def test_with_timestamps(self) -> None:
        now = datetime.now(tz=UTC)
        info = WorkloadStatusInfo(
            id="1",
            name="web",
            image="nginx",
            status="stopped",
            started_at=now,
            stopped_at=now,
            exit_code=0,
        )
        assert info.started_at == now
        assert info.stopped_at == now

    def test_with_restarts(self) -> None:
        info = WorkloadStatusInfo(
            id="1", name="web", image="nginx", status="running", restarts=5
        )
        assert info.restarts == 5

    def test_error_state(self) -> None:
        info = WorkloadStatusInfo(
            id="1",
            name="crash",
            image="bad",
            status="error",
            exit_code=1,
            message="segfault",
        )
        assert info.status == "error"
        assert info.exit_code == 1
        assert info.message == "segfault"
