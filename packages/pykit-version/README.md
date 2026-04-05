# pykit-version

Build metadata and version info aggregation from package metadata, git state, and Python runtime.

## Installation

```bash
pip install pykit-version
# or
uv add pykit-version
```

## Quick Start

```python
from pykit_version import VersionInfo, get_version_info, get_short_version, get_full_version

# Full version info snapshot
info = get_version_info("my-service")
print(info.version)         # "1.2.0" or "dev"
print(info.git_commit)      # "a1b2c3d"
print(info.git_branch)      # "main"
print(info.python_version)  # "3.13.0 (default, ...)"
print(info.is_release)      # True (not "dev", not dirty)
print(info.is_dirty)        # False

# Short version string
print(get_short_version("my-service"))  # "1.2.0-a1b2c3d"

# Full version string with metadata
print(get_full_version("my-service"))
# "1.2.0-a1b2c3d (built 2024-01-15T10:30:00+00:00)"
# or with branch: "1.2.0-a1b2c3d-feature-x (built ...)"
```

## Key Components

- **VersionInfo** — Frozen dataclass with `version`, `git_commit`, `git_branch`, `build_time`, `python_version`, `is_release`, and `is_dirty` fields
- **get_version_info()** — Collect complete version metadata from package info, git, and runtime (gracefully handles missing git)
- **get_short_version()** — Concise version string: `{version}[-{commit}][-dirty]`
- **get_full_version()** — Detailed string with optional branch (if not main/master) and build time

## Dependencies

None — zero external dependencies (uses stdlib `importlib.metadata` and `subprocess`).

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
