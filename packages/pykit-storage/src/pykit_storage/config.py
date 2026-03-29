"""Storage configuration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StorageConfig:
    """Configuration for the storage component."""

    name: str = "storage"
    provider: str = "local"  # local | s3
    enabled: bool = True
    base_path: str = "./storage"
    max_file_size: int = 104_857_600  # 100 MB
    public_url: str = ""
    allowed_types: list[str] = field(default_factory=list)
