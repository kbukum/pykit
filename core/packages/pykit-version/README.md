# pykit-version

Collect package, git, build, and Python runtime metadata into a small version-reporting API.

## Installation

```bash
pip install pykit-version
# or
uv add pykit-version
```

## Quick start

```python
from pykit_version import get_full_version, get_short_version, get_version_info

info = get_version_info("my-service")
print(info.version)
print(info.git_commit)
print(info.git_branch)
print(info.python_version)
print(info.is_release)
print(info.is_dirty)

print(get_short_version("my-service"))
print(get_full_version("my-service"))
```

## Core APIs

- **`VersionInfo`** stores version, git commit, git branch, build time, Python version, release status, and dirty-tree status.
- **`get_version_info()`** collects metadata from package metadata, git state, and the running interpreter.
- **`get_short_version()`** returns `{version}[-{commit}][-dirty]`.
- **`get_full_version()`** adds branch and build-time details when available.

## Dependencies

None. The package uses standard-library modules such as `importlib.metadata` and `subprocess`.

## See also

- [Main pykit README](../../../README.md)
- [tests/](tests/)
