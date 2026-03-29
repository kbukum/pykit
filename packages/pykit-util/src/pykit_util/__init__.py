"""pykit-util — pure-Python utility helpers (zero dependencies)."""

__version__ = "0.1.0"

from pykit_util.collections import chunk, first, flatten, group_by, unique
from pykit_util.merge import deep_merge
from pykit_util.parse import mask_secret, parse_bool, parse_size
from pykit_util.sanitize import is_safe_string, sanitize_env_value, sanitize_string
from pykit_util.strings import coalesce, slug, truncate

__all__ = [
    # collections
    "chunk",
    # strings
    "coalesce",
    # merge
    "deep_merge",
    "first",
    "flatten",
    "group_by",
    # sanitize
    "is_safe_string",
    # parse
    "mask_secret",
    "parse_bool",
    "parse_size",
    "sanitize_env_value",
    "sanitize_string",
    "slug",
    "truncate",
    "unique",
]
