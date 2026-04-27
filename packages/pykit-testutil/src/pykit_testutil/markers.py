"""pytest marker utilities for pykit test suites."""
from __future__ import annotations

import pytest

# Convenience re-exports for common marks
integration = pytest.mark.integration
"""Mark a test as requiring live services (Redis, PostgreSQL, Kafka, etc.)"""

slow = pytest.mark.slow
"""Mark a test as slow-running (> 1 second). Skipped with -m 'not slow'."""

requires_network = pytest.mark.requires_network
"""Mark a test as requiring network access."""

__all__ = ["integration", "slow", "requires_network"]
