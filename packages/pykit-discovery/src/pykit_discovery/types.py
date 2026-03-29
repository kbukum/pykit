"""Service instance type for discovery."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ServiceInstance:
    """A discovered service endpoint."""

    id: str
    name: str
    host: str
    port: int
    metadata: dict[str, str] = field(default_factory=dict)
    healthy: bool = True

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"

    def url(self, scheme: str = "http") -> str:
        return f"{scheme}://{self.host}:{self.port}"
