"""Bootstrap-time address resolution utilities.

:func:`resolve_addr` resolves a service name to a ``(host, port)`` pair using
the :class:`~pykit_discovery.protocols.Discovery` protocol. Intended for
one-shot infrastructure resolution at startup — before connection pools are
created — not for runtime load balancing.
"""

from __future__ import annotations

from pykit_discovery.protocols import Discovery


async def resolve_addr(disc: Discovery, service_name: str) -> tuple[str, int]:
    """Resolve a service name to a ``(host, port)`` pair via service discovery.

    Returns the first healthy instance's host and port. Use at bootstrap time
    to resolve infrastructure addresses (database, cache, kafka, etc.) before
    connection pools are created.

    Args:
        disc: A discovery provider implementing the Discovery protocol.
        service_name: The service name to resolve (e.g. ``"postgres-dev"``).

    Returns:
        A ``(host, port)`` tuple for the resolved service.

    Raises:
        ValueError: If no healthy instances are found.
    """
    instances = await disc.discover(service_name)
    if not instances:
        raise ValueError(f'resolve "{service_name}": no healthy instances found')

    inst = instances[0]
    return inst.host, inst.port
