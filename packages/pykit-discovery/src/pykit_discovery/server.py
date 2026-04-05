"""Discovery-integrated server component — auto-register/deregister with discovery."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from pykit_component import Health, HealthStatus
from pykit_discovery.protocols import Registry
from pykit_discovery.types import ServiceInstance


class DiscoveryServer:
    """Wraps any server component with discovery auto-registration.

    On `start()`, the inner server starts first, then registers with discovery.
    On `stop()`, deregisters from discovery first, then stops the server.
    """

    def __init__(
        self,
        server: object,  # Any object with start/stop/health methods
        registry: Registry,
        instance: ServiceInstance,
        name: str = "discovery-server",
    ) -> None:
        """Initialize a discovery-integrated server.

        Args:
            server: The inner server component with start(), stop(), and health() methods
            registry: The service registry for registration/deregistration
            instance: The service instance configuration for registration
            name: Component name for logging and identification
        """
        self.server = server
        self.registry = registry
        self.instance = instance
        self.name = name
        self.logger = logging.getLogger(__name__)

    @property
    def instance_id(self) -> str:
        """Get the service instance ID."""
        return self.instance.id

    @property
    def service_name(self) -> str:
        """Get the logical service name."""
        return self.instance.name

    async def start(self) -> None:
        """Start the inner server, then register with discovery."""
        self.logger.info(
            "Starting %s component",
            self.name,
            extra={
                "service_id": self.instance.id,
                "service_name": self.instance.name,
            },
        )

        # Start the inner server first
        try:
            if hasattr(self.server, "start"):
                await self.server.start()
            else:
                raise AttributeError(f"Server {self.server} has no start() method")
        except Exception as e:
            self.logger.error("Failed to start inner server: %s", e)
            raise

        # Then register with discovery
        self.logger.info(
            "Registering service with discovery",
            extra={
                "service_id": self.instance.id,
                "service_name": self.instance.name,
                "address": self.instance.host,
                "port": self.instance.port,
            },
        )

        try:
            await self.registry.register(self.instance)
        except Exception as e:
            self.logger.error(
                "Failed to register with discovery: %s, stopping inner server",
                e,
            )
            # Attempt to stop the server if registration fails
            try:
                if hasattr(self.server, "stop"):
                    await self.server.stop()
            except Exception as stop_error:
                self.logger.warning("Failed to stop server after registration failure: %s", stop_error)
            raise

        self.logger.info(
            "Service registered successfully",
            extra={"service_id": self.instance.id},
        )

    async def stop(self) -> None:
        """Deregister from discovery, then stop the inner server."""
        self.logger.info(
            "Stopping %s component",
            self.name,
            extra={"service_id": self.instance.id},
        )

        # Deregister from discovery first
        try:
            await self.registry.deregister(self.instance.id)
        except Exception as e:
            self.logger.warning(
                "Failed to deregister from discovery: %s (continuing with server stop)",
                e,
            )
            # Continue to stop the server even if deregistration fails

        # Then stop the inner server
        try:
            if hasattr(self.server, "stop"):
                await self.server.stop()
        except Exception as e:
            self.logger.error("Failed to stop inner server: %s", e)
            raise

        self.logger.info(
            "%s component stopped",
            self.name,
            extra={"service_id": self.instance.id},
        )

    async def health(self) -> Health:
        """Return component health (delegates to inner component + discovery status)."""
        # Try to get health from inner component if it has one
        if hasattr(self.server, "health"):
            try:
                inner_health = await self.server.health()
                # Assume it's a Health object if it has status attribute
                if hasattr(inner_health, "status"):
                    if inner_health.status == HealthStatus.HEALTHY:
                        return Health(
                            name=self.name,
                            status=HealthStatus.HEALTHY,
                            message=f"server healthy; registered as {self.instance.name}",
                            timestamp=datetime.now(UTC),
                        )
                    else:
                        return Health(
                            name=self.name,
                            status=HealthStatus.UNHEALTHY,
                            message=f"server unhealthy: {inner_health.message}",
                            timestamp=datetime.now(UTC),
                        )
            except Exception as e:
                self.logger.warning("Failed to get health from inner component: %s", e)

        # Default healthy status
        return Health(
            name=self.name,
            status=HealthStatus.HEALTHY,
            message="running",
            timestamp=datetime.now(UTC),
        )
