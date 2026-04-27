"""Discovery component — lifecycle wrapper for service discovery.

Mirrors gokit's ``discovery.Component`` and rskit's ``DiscoveryComponent``.
Services create one instance from their ``DiscoveryConfig`` — the component
handles provider creation, registration, and deregistration automatically.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pykit_component import Health, HealthStatus
from pykit_discovery.factory import ProviderPair, create_provider, init_builtin
from pykit_discovery.protocols import Discovery, Registry

if TYPE_CHECKING:
    from pykit_discovery.config import DiscoveryConfig
    from pykit_discovery.types import ServiceInstance

logger = logging.getLogger(__name__)


class DiscoveryComponent:
    """Config-driven discovery component with full lifecycle management.

    Usage::

        comp = DiscoveryComponent(config)
        await comp.start()     # creates provider, registers if enabled
        comp.discovery          # → generic Discovery interface
        comp.registry           # → generic Registry interface
        await comp.stop()      # deregisters, closes resources
    """

    def __init__(
        self,
        config: DiscoveryConfig | None = None,
        *,
        provider: object | None = None,
    ) -> None:
        from pykit_discovery.config import DiscoveryConfig as _DiscoveryConfig
        from pykit_discovery.factory import ProviderPair
        from pykit_discovery.static import StaticProvider

        if provider is not None:
            # Direct provider supplied — use it immediately without lifecycle.
            self._config = config if config is not None else _DiscoveryConfig(enabled=True)
            self._pair: ProviderPair | None = ProviderPair(
                registry=provider,  # type: ignore[arg-type]
                discovery=provider,  # type: ignore[arg-type]
            )
        elif config is None:
            # No config or provider — default to an in-memory StaticProvider.
            self._config = _DiscoveryConfig(enabled=True)
            _default = StaticProvider()
            self._pair = ProviderPair(registry=_default, discovery=_default)
        else:
            self._config = config
            self._pair = None
        self._instance_id: str | None = None
        self._started = False

    @property
    def name(self) -> str:
        return "discovery"

    @property
    def discovery(self) -> Discovery:
        """Return the generic discovery interface."""
        if self._pair is None:
            raise RuntimeError("DiscoveryComponent not started")
        return self._pair.discovery

    @property
    def registry(self) -> Registry:
        """Return the generic registry interface."""
        if self._pair is None:
            raise RuntimeError("DiscoveryComponent not started")
        return self._pair.registry

    async def start(self) -> None:
        """Initialize provider via factory and register if enabled."""
        init_builtin()

        if not self._config.enabled:
            logger.info("discovery disabled — skipping provider init")
            self._started = True
            return

        try:
            self._pair = create_provider(self._config)
            logger.info("discovery provider created: %s", self._config.provider)
        except Exception:
            logger.exception("failed to create discovery provider")
            self._started = True
            return

        if self._config.registration.enabled:
            instance = self._config.build_instance()
            self._instance_id = instance.id

            max_retries = max(self._config.registration.max_retries, 1)
            interval = self._config.registration.retry_seconds()
            last_err: Exception | None = None

            for attempt in range(1, max_retries + 1):
                try:
                    await self._pair.registry.register(instance)
                    logger.info(
                        "registered service %s (%s)",
                        instance.name,
                        self._instance_id,
                    )
                    last_err = None
                    break
                except Exception as exc:
                    last_err = exc
                    logger.warning(
                        "failed to register service (attempt %d/%d): %s",
                        attempt,
                        max_retries,
                        exc,
                    )
                    if attempt < max_retries:
                        await asyncio.sleep(interval)
                        interval *= 2  # exponential backoff

            if last_err is not None:
                if self._config.registration.required:
                    raise RuntimeError(
                        f"discovery: register self after {max_retries} retries: {last_err}"
                    ) from last_err
                logger.warning("failed to register with discovery — continuing in degraded mode")

        self._started = True

    async def stop(self) -> None:
        """Deregister and release resources."""
        if self._instance_id and self._pair:
            try:
                await self._pair.registry.deregister(self._instance_id)
                logger.info("deregistered service %s", self._instance_id)
            except Exception:
                logger.warning("failed to deregister from discovery", exc_info=True)

        if self._pair:
            await self._pair.close()
            self._pair = None

        self._instance_id = None
        self._started = False

    async def health(self) -> Health:
        if not self._started:
            return Health(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message="not started",
                timestamp=datetime.now(UTC),
            )

        if not self._config.enabled:
            return Health(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message="disabled",
                timestamp=datetime.now(UTC),
            )

        if self._pair is None:
            return Health(
                name=self.name,
                status=HealthStatus.DEGRADED,
                message="provider init failed",
                timestamp=datetime.now(UTC),
            )

        msg = "running"
        if self._instance_id:
            msg = f"registered as {self._instance_id}"

        return Health(
            name=self.name,
            status=HealthStatus.HEALTHY,
            message=msg,
            timestamp=datetime.now(UTC),
        )

    async def register(self, instance: ServiceInstance) -> None:
        """Delegate to the underlying registry."""
        if self._pair is None:
            raise RuntimeError("DiscoveryComponent not started")
        await self._pair.registry.register(instance)

    async def deregister(self, instance_id: str) -> None:
        """Delegate to the underlying registry."""
        if self._pair is None:
            raise RuntimeError("DiscoveryComponent not started")
        await self._pair.registry.deregister(instance_id)

    async def discover(self, service_name: str) -> list:
        """Delegate to the underlying discovery."""
        if self._pair is None:
            raise RuntimeError("DiscoveryComponent not started")
        return await self._pair.discovery.discover(service_name)
