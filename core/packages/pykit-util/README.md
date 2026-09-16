# pykit-util

Use small, dependency-free helpers for clocks, collections, JSON, parsing, sanitization, merging, and strings.

## Installation

```bash
pip install pykit-util
# or
uv add pykit-util
```

## Quick start

```python
from pykit_util import (
    chunk,
    coalesce,
    deep_merge,
    first,
    flatten,
    group_by,
    mask_secret,
    parse_size,
    slug,
    truncate,
    unique,
)

first([3, 1, 4], predicate=lambda x: x > 2)
unique([1, 2, 2, 3, 1])
chunk([1, 2, 3, 4, 5], 2)
flatten([[1, 2], [3], [4, 5]])
group_by(["hi", "hey", "bye"], lambda s: s[0])
deep_merge({"a": {"x": 1}}, {"a": {"y": 2}})
parse_size("512MB")
mask_secret("sk-abc123-secret")
slug("Hello World!")
truncate("long text here", 10)
coalesce(None, "", "fallback")
```

## What it includes

- **Collections:** `first()`, `unique()`, `chunk()`, `flatten()`, and `group_by()`.
- **Merging:** `deep_merge()` returns a new recursively merged dictionary.
- **Parsing:** `parse_size()`, `parse_bool()`, and `mask_secret()`.
- **Sanitization:** `sanitize_string()`, `sanitize_env_value()`, and `is_safe_string()`.
- **Strings:** `coalesce()`, `slug()`, and `truncate()`.
- **Time and codecs:** `Clock`, `SystemClock`, `FakeClock`, `Codec`, and `JsonCodec`.
- **Registry:** `Registry` for lightweight async or sync keyed registration.

## Dependencies

None. This package is pure Python and uses no external runtime dependencies.

## See also

- [Main pykit README](../../../README.md)
- [tests/](tests/)
