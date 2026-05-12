# pykit-util

Pure-Python utility helpers with zero dependencies: collections, string manipulation, parsing, sanitization, and deep merge.

## Installation

```bash
pip install pykit-util
# or
uv add pykit-util
```

## Quick Start

```python
from pykit_util import (
    first, unique, chunk, flatten, group_by,
    deep_merge, parse_size, mask_secret, slug, truncate, coalesce,
)

# Collection helpers
first([3, 1, 4], predicate=lambda x: x > 2)  # 3
unique([1, 2, 2, 3, 1])                       # [1, 2, 3]
chunk([1, 2, 3, 4, 5], 2)                     # [[1, 2], [3, 4], [5]]
flatten([[1, 2], [3], [4, 5]])                 # [1, 2, 3, 4, 5]
group_by(["hi", "hey", "bye"], lambda s: s[0]) # {"h": ["hi", "hey"], "b": ["bye"]}

# Dict merging
deep_merge({"a": {"x": 1}}, {"a": {"y": 2}})  # {"a": {"x": 1, "y": 2}}

# Parsing
parse_size("512MB")     # 536870912
mask_secret("sk-abc123-secret")  # "sk-a************"
slug("Hello World!")    # "hello-world"
truncate("long text here", 10)  # "long te..."
coalesce(None, "", "fallback")  # "fallback"
```

## Key Components

- **first()** — Return first item matching a predicate (or default)
- **unique()** — Deduplicate preserving insertion order
- **chunk()** — Split into sub-lists of at most N elements
- **flatten()** — Flatten one level of nesting
- **group_by()** — Group items into a dict keyed by a function
- **deep_merge()** — Recursively merge dicts (override wins, returns new dict)
- **parse_size()** — Parse human-readable sizes ("10MB") into bytes
- **parse_bool()** — Parse boolean strings (raises ValueError on invalid input)
- **mask_secret()** — Mask a secret string, keeping a visible prefix
- **sanitize_string()** — Trim whitespace and remove control characters (NFC normalized)
- **sanitize_env_value()** — Strip surrounding quotes from env-var values
- **is_safe_string()** — Basic injection pattern check (defense-in-depth only)
- **coalesce()** — Return first truthy value
- **slug()** — Convert text to URL-safe slug
- **truncate()** — Truncate text with suffix

## Dependencies

None — zero external dependencies.

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples
