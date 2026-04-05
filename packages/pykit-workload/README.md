# pykit-workload

Provider-based workload manager for deploying, monitoring, and controlling containerized workloads (Docker, Kubernetes).

## Installation

```bash
pip install pykit-workload
# or
uv add pykit-workload
```

## Quick Start

```python
from pykit_workload import (
    WorkloadConfig, create_manager, register_factory,
    DeployRequest, ResourceConfig, PortMapping,
    WorkloadStatus, LogOptions, ListFilter,
)

# Create a manager for your provider
config = WorkloadConfig(provider="docker", enabled=True)
manager = create_manager(config, provider_cfg=my_docker_config)

# Deploy a workload
result = await manager.deploy(DeployRequest(
    name="web-api",
    image="myapp:latest",
    resources=ResourceConfig(cpu_request="500m", memory_request="256Mi"),
    ports=[PortMapping(host_port=8080, container_port=80)],
    env={"DATABASE_URL": "postgres://..."},
    labels={"team": "platform"},
))
print(f"Deployed: {result.id}, status={result.status}")

# Monitor and manage
status = await manager.status(result.id)
logs = await manager.logs(result.id, LogOptions(tail=100))
workloads = await manager.list(ListFilter(labels={"team": "platform"}))

await manager.restart(result.id)
await manager.stop(result.id)
await manager.remove(result.id)
```

### Resource Parsing Utilities

```python
from pykit_workload import parse_memory, parse_cpu, format_memory, format_cpu

parse_memory("512Mi")  # 536870912 (bytes)
parse_cpu("500m")      # 500000000 (nanocores)
format_memory(536870912)  # "512.0Mi"
format_cpu(500000000)     # "500m"
```

## Key Components

- **Manager** — Protocol for workload lifecycle: `deploy`, `stop`, `remove`, `restart`, `status`, `wait`, `logs`, `list`, `health_check`
- **ExecProvider** — Optional protocol for in-container command execution (`exec`)
- **StatsProvider** — Optional protocol for resource usage stats (`stats`)
- **DeployRequest** — Complete deployment specification with image, resources, ports, volumes, env, labels
- **WorkloadConfig** — Configuration with provider type, enabled flag, and default labels
- **create_manager() / register_factory()** — Factory pattern for pluggable provider backends
- **ResourceConfig / NetworkConfig / PortMapping / VolumeMount** — Kubernetes-style resource and networking configuration
- **WorkloadStatus** — Lifecycle enum: `CREATED`, `RUNNING`, `STOPPED`, `COMPLETED`, `ERROR`, `RESTARTING`
- **parse_memory() / parse_cpu()** — Parse Kubernetes-style resource strings to bytes/nanocores

## Dependencies

- `pykit-errors`, `pykit-component`

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
