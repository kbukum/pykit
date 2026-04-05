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
    protocol: str = "grpc"
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    healthy: bool = True
    weight: int = 1

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"

    @property
    def endpoint(self) -> str:
        """Alias for address — matches Go/Rust naming."""
        return self.address

    def url(self, scheme: str = "http") -> str:
        return f"{scheme}://{self.host}:{self.port}"
