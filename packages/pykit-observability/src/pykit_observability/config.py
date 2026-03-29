"""Configuration dataclasses for tracing and metrics setup."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TracerConfig:
    """Configuration for OpenTelemetry tracing."""

    service_name: str
    endpoint: str = ""
    sample_rate: float = 1.0
    enabled: bool = True


@dataclass
class MeterConfig:
    """Configuration for OpenTelemetry metrics."""

    service_name: str
    endpoint: str = ""
    export_interval: float = 60.0
    enabled: bool = True
