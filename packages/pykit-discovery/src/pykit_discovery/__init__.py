"""pykit-discovery — service discovery and load balancing."""

from pykit_discovery.component import DiscoveryComponent
from pykit_discovery.config import (
    DiscoveredService,
    DiscoveryConfig,
    HealthConfig,
    RegistrationConfig,
    StaticEndpoint,
)
from pykit_discovery.consul import ConsulProvider
from pykit_discovery.factory import (
    ProviderFactory,
    ProviderPair,
    create_provider,
    init_builtin,
    register_provider,
)
from pykit_discovery.protocols import Discovery, Registry, Watcher
from pykit_discovery.resolve import resolve_addr
from pykit_discovery.server import DiscoveryServer
from pykit_discovery.static import StaticProvider
from pykit_discovery.strategy import (
    LeastConnectionsStrategy,
    LoadBalancer,
    RandomStrategy,
    RoundRobinStrategy,
)
from pykit_discovery.types import ServiceInstance

__all__ = [
    "ConsulProvider",
    "DiscoveredService",
    "Discovery",
    "DiscoveryComponent",
    "DiscoveryConfig",
    "DiscoveryServer",
    "HealthConfig",
    "LeastConnectionsStrategy",
    "LoadBalancer",
    "ProviderFactory",
    "ProviderPair",
    "RandomStrategy",
    "RegistrationConfig",
    "Registry",
    "RoundRobinStrategy",
    "ServiceInstance",
    "StaticEndpoint",
    "StaticProvider",
    "Watcher",
    "create_provider",
    "init_builtin",
    "register_provider",
    "resolve_addr",
]
__version__ = "0.1.0"
