"""pykit-discovery — service discovery and load balancing."""

from pykit_discovery.component import DiscoveryComponent
from pykit_discovery.consul import ConsulProvider
from pykit_discovery.protocols import Discovery, Registry
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
    "Discovery",
    "DiscoveryComponent",
    "DiscoveryServer",
    "LeastConnectionsStrategy",
    "LoadBalancer",
    "RandomStrategy",
    "Registry",
    "RoundRobinStrategy",
    "ServiceInstance",
    "StaticProvider",
]
__version__ = "0.1.0"
