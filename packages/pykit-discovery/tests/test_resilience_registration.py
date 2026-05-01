"""Tests for resilience-backed discovery registration."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from pykit_discovery.component import DiscoveryComponent
from pykit_discovery.config import DiscoveryConfig, RegistrationConfig
from pykit_discovery.factory import ProviderPair
from pykit_discovery.static import StaticProvider


class _FlakyProvider(StaticProvider):
    def __init__(self) -> None:
        super().__init__()
        self.attempts = 0

    async def register(self, instance) -> None:
        self.attempts += 1
        if self.attempts < 3:
            raise RuntimeError("temporary registration error")
        await super().register(instance)


@pytest.mark.asyncio
async def test_registration_retries_with_resilience() -> None:
    provider = _FlakyProvider()
    component = DiscoveryComponent(
        config=DiscoveryConfig(
            enabled=True,
            registration=RegistrationConfig(
                enabled=True,
                required=True,
                max_retries=3,
                retry_interval="0s",
                service_name="svc",
                service_id="svc-1",
                service_address="127.0.0.1",
                service_port=8080,
            ),
        ),
    )

    with patch(
        "pykit_discovery.component.create_provider",
        return_value=ProviderPair(registry=provider, discovery=provider),
    ):
        await component.start()

    assert provider.attempts == 3
    await component.stop()
