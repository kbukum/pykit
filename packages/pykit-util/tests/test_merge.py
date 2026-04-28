"""Tests for pykit_util deep_merge."""

from pykit_util import deep_merge


class TestDeepMerge:
    def test_shallow(self) -> None:
        assert deep_merge({"a": 1, "b": 2}, {"b": 3, "c": 4}) == {"a": 1, "b": 3, "c": 4}

    def test_nested(self) -> None:
        base = {"db": {"host": "localhost", "port": 5432}}
        over = {"db": {"port": 3306, "name": "mydb"}}
        assert deep_merge(base, over) == {"db": {"host": "localhost", "port": 3306, "name": "mydb"}}

    def test_override_replaces_non_dict(self) -> None:
        assert deep_merge({"a": 1}, {"a": [1, 2, 3]}) == {"a": [1, 2, 3]}

    def test_empty_base(self) -> None:
        assert deep_merge({}, {"a": 1}) == {"a": 1}

    def test_empty_override(self) -> None:
        assert deep_merge({"a": 1}, {}) == {"a": 1}

    def test_deeply_nested(self) -> None:
        base = {"l1": {"l2": {"l3": {"a": 1}}}}
        over = {"l1": {"l2": {"l3": {"b": 2}}}}
        assert deep_merge(base, over) == {"l1": {"l2": {"l3": {"a": 1, "b": 2}}}}

    def test_does_not_mutate(self) -> None:
        base = {"a": 1}
        over = {"b": 2}
        _ = deep_merge(base, over)
        assert base == {"a": 1}
        assert over == {"b": 2}
