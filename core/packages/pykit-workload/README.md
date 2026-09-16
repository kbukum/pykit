# pykit-workload

Describe and manage container-style workloads through a provider registry and typed lifecycle models.

## Installation

```bash
pip install pykit-workload
# or
uv add pykit-workload
```

## Quick start

```python
from pykit_workload import (
    DeployRequest,
    ListFilter,
    LogOptions,
    PortMapping,
    ResourceConfig,
    WorkloadConfig,
    create_manager,
    register_factory,
)

register_factory("docker", docker_manager_factory)

config = WorkloadConfig(provider="docker", enabled=True)
manager = create_manager(config, provider_cfg=my_docker_config)

result = await manager.deploy(
    DeployRequest(
        name="web-api",
        image="myapp:latest",
        resources=ResourceConfig(cpu_request="500m", memory_request="256Mi"),
        ports=[PortMapping(host=8080, container=80)],
        environment={"DATABASE_URL": "postgres://..."},
        labels={"team": "platform"},
    )
)

status = await manager.status(result.id)
logs = await manager.logs(result.id, LogOptions(tail=100))
workloads = await manager.list(ListFilter(labels={"team": "platform"}))

await manager.restart(result.id)
await manager.stop(result.id)
await manager.remove(result.id)
```

## Resource helpers

```python
from pykit_workload import format_cpu, format_memory, parse_cpu, parse_memory

parse_memory("512Mi")
parse_cpu("500m")
format_memory(536870912)
format_cpu(500000000)
```

## Core APIs

- **`Manager`** defines workload lifecycle methods such as `deploy`, `stop`, `remove`, `restart`, `status`, `wait`, `logs`, `list`, and `health_check`.
- **`ExecProvider`** and **`StatsProvider`** add optional execution and metrics capabilities.
- **`WorkloadConfig`**, **`register_factory()`**, and **`create_manager()`** provide config-driven backend selection.
- **`DeployRequest`**, **`DeployResult`**, **`WorkloadInfo`**, and **`WorkloadStatusInfo`** model deployment and runtime state.
- **`ResourceConfig`**, **`NetworkConfig`**, **`PortMapping`**, and **`VolumeMount`** model resource and networking inputs.
- **`parse_memory()`**, **`parse_cpu()`**, **`format_memory()`**, and **`format_cpu()`** convert Kubernetes-style resource values.

## Dependencies

- `pykit-errors`
- `pykit-component`

## See also

- [Main pykit README](../../../README.md)
- [tests/](tests/)
