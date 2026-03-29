"""Collection utilities — pure Python, zero dependencies."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable


def first[T](
    iterable: Iterable[T], predicate: Callable[[T], bool] | None = None, default: T | None = None
) -> T | None:
    """Return the first item matching *predicate*, or *default*."""
    for item in iterable:
        if predicate is None or predicate(item):
            return item
    return default


def unique[T](items: Iterable[T]) -> list[T]:
    """Deduplicate *items* while preserving insertion order."""
    seen: set[T] = set()
    result: list[T] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def chunk[T](items: list[T], size: int) -> list[list[T]]:
    """Split *items* into sub-lists of at most *size* elements."""
    if size <= 0:
        raise ValueError("chunk size must be positive")
    return [items[i : i + size] for i in range(0, len(items), size)]


def flatten[T](nested: Iterable[Iterable[T]]) -> list[T]:
    """Flatten one level of nesting."""
    result: list[T] = []
    for sub in nested:
        result.extend(sub)
    return result


def group_by[K, V](items: Iterable[V], key_fn: Callable[[V], K]) -> dict[K, list[V]]:
    """Group *items* into a dict keyed by *key_fn*."""
    groups: dict[K, list[V]] = defaultdict(list)
    for item in items:
        groups[key_fn(item)].append(item)
    return dict(groups)
