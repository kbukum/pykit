"""Consul-backed service discovery and registry."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from pykit_discovery.types import ServiceInstance

logger = logging.getLogger(__name__)


class ConsulProvider:
    """Consul-backed service discovery and registry.

    Uses Consul HTTP API v1 for service registration and discovery.
    """

    def __init__(
        self,
        address: str = "localhost:8500",
        scheme: str = "http",
        token: str | None = None,
        dc: str | None = None,
    ) -> None:
        self._base_url = f"{scheme}://{address}"
        self._dc = dc
        headers: dict[str, str] = {}
        if token:
            headers["X-Consul-Token"] = token
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
        )

    async def register(self, instance: ServiceInstance) -> None:
        """Register service with Consul agent.

        Sends a PUT to ``/v1/agent/service/register``.  When the instance
        metadata contains a ``health_url`` key an HTTP health check is
        attached to the registration payload.
        """
        payload: dict[str, Any] = {
            "ID": instance.id,
            "Name": instance.name,
            "Address": instance.host,
            "Port": instance.port,
            "Meta": instance.metadata,
        }

        health_url = instance.metadata.get("health_url")
        if health_url:
            payload["Check"] = {
                "HTTP": health_url,
                "Interval": "10s",
                "Timeout": "5s",
                "DeregisterCriticalServiceAfter": "1m",
            }

        try:
            resp = await self._client.put("/v1/agent/service/register", json=payload)
            resp.raise_for_status()
            logger.info("registered service %s (%s)", instance.name, instance.id)
        except httpx.HTTPError as exc:
            logger.warning("failed to register service %s: %s", instance.id, exc)
            raise

    async def deregister(self, instance_id: str) -> None:
        """Deregister service from Consul agent.

        Sends a PUT to ``/v1/agent/service/deregister/{instance_id}``.
        """
        try:
            resp = await self._client.put(
                f"/v1/agent/service/deregister/{instance_id}",
            )
            resp.raise_for_status()
            logger.info("deregistered service %s", instance_id)
        except httpx.HTTPError:
            logger.exception("failed to deregister service %s", instance_id)
            raise

    async def discover(self, service_name: str) -> list[ServiceInstance]:
        """Discover healthy instances via Consul.

        Queries ``/v1/health/service/{service_name}?passing=true`` and
        converts the response into a list of ``ServiceInstance`` objects.
        """
        params: dict[str, str] = {"passing": "true"}
        if self._dc:
            params["dc"] = self._dc

        try:
            resp = await self._client.get(
                f"/v1/health/service/{service_name}",
                params=params,
            )
            resp.raise_for_status()
        except httpx.HTTPError:
            logger.exception("failed to discover service %s", service_name)
            return []

        instances: list[ServiceInstance] = []
        for entry in resp.json():
            svc: dict[str, Any] = entry["Service"]
            instances.append(
                ServiceInstance(
                    id=svc["ID"],
                    name=svc["Service"],
                    host=svc["Address"],
                    port=svc["Port"],
                    metadata=svc.get("Meta") or {},
                    healthy=True,
                ),
            )
        return instances

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
