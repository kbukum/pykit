"""Discovery configuration — mirrors gokit's discovery.Config."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pykit_discovery.types import ServiceInstance


@dataclass(frozen=True)
class RegistrationConfig:
    """Self-registration settings."""

    enabled: bool = False
    required: bool = True
    max_retries: int = 3
    retry_interval: str = "2s"
    service_name: str = ""
    service_id: str = ""
    service_address: str = ""
    service_port: int = 0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    def effective_id(self) -> str:
        """Return service_id, falling back to service_name."""
        return self.service_id or self.service_name

    def retry_seconds(self) -> float:
        """Parse retry_interval as seconds."""
        s = self.retry_interval.strip()
        if s.endswith("ms"):
            return float(s[:-2]) / 1000
        if s.endswith("s"):
            return float(s[:-1])
        if s.endswith("m"):
            return float(s[:-1]) * 60
        try:
            return float(s)
        except ValueError:
            return 2.0


@dataclass(frozen=True)
class HealthConfig:
    """Health check settings for registered services."""

    enabled: bool = True
    type: str = "http"
    path: str = "/health"
    interval: str = "10s"
    timeout: str = "5s"
    deregister_after: str = "1m"


@dataclass(frozen=True)
class DiscoveredService:
    """A remote service this application depends on."""

    name: str = ""
    protocol: str = "grpc"


@dataclass(frozen=True)
class StaticEndpoint:
    """A statically configured endpoint (fallback or static provider)."""

    name: str = ""
    address: str = ""
    port: int = 0
    protocol: str = "grpc"
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    weight: int = 1
    healthy: bool = True


@dataclass(frozen=True)
class DiscoveryConfig:
    """Top-level discovery configuration.

    Mirrors gokit's ``discovery.Config`` — all three kits use the same
    config shape so services are structurally identical regardless of language.
    """

    enabled: bool = False
    provider: str = "static"
    addr: str = ""
    scheme: str = "http"
    token: str = ""
    provider_options: dict[str, Any] = field(default_factory=dict)
    registration: RegistrationConfig = field(default_factory=RegistrationConfig)
    health: HealthConfig = field(default_factory=HealthConfig)
    cache_ttl: str = "30s"
    services: list[DiscoveredService] = field(default_factory=list)
    static_endpoints: list[StaticEndpoint] = field(default_factory=list)

    def validate(self) -> None:
        """Validate that required fields are present.

        Raises:
            ValueError: If required fields are missing.
        """
        if not self.enabled:
            return
        if self.registration.enabled:
            if not self.registration.service_name:
                raise ValueError("discovery.registration.service_name is required")
            if self.registration.service_port <= 0:
                raise ValueError("discovery.registration.service_port must be > 0")

    def build_instance(self) -> ServiceInstance:
        """Build a ServiceInstance from the registration config."""
        reg = self.registration
        return ServiceInstance(
            id=reg.effective_id(),
            name=reg.service_name,
            host=reg.service_address,
            port=reg.service_port,
            tags=list(reg.tags),
            metadata=dict(reg.metadata),
        )
