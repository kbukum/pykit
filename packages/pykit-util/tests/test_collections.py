"""Tests for pykit_util.collections."""

from pykit_util import chunk, first, flatten, group_by, unique


class TestFirst:
    def test_no_predicate(self) -> None:
        assert first([1, 2, 3]) == 1

    def test_with_predicate(self) -> None:
        assert first([1, 2, 3, 4], predicate=lambda x: x > 2) == 3

    def test_empty(self) -> None:
        assert first([], default=42) == 42

    def test_no_match(self) -> None:
        assert first([1, 2], predicate=lambda x: x > 10, default=-1) == -1


class TestUnique:
    def test_basic(self) -> None:
        assert unique([1, 2, 2, 3, 1]) == [1, 2, 3]

    def test_preserves_order(self) -> None:
        assert unique([3, 1, 2, 1, 3]) == [3, 1, 2]

    def test_empty(self) -> None:
        assert unique([]) == []

    def test_strings(self) -> None:
        assert unique(["a", "b", "a"]) == ["a", "b"]


class TestChunk:
    def test_even_split(self) -> None:
        assert chunk([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]

    def test_uneven_split(self) -> None:
        assert chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]

    def test_single_element_chunks(self) -> None:
        assert chunk([1, 2, 3], 1) == [[1], [2], [3]]

    def test_chunk_larger_than_list(self) -> None:
        assert chunk([1, 2], 10) == [[1, 2]]

    def test_empty(self) -> None:
        assert chunk([], 3) == []


class TestFlatten:
    def test_basic(self) -> None:
        assert flatten([[1, 2], [3, 4]]) == [1, 2, 3, 4]

    def test_empty_sublists(self) -> None:
        assert flatten([[], [1], []]) == [1]

    def test_empty(self) -> None:
        assert flatten([]) == []


class TestGroupBy:
    def test_basic(self) -> None:
        result = group_by(["ant", "bear", "ape", "bat"], key_fn=lambda s: s[0])
        assert result == {"a": ["ant", "ape"], "b": ["bear", "bat"]}

    def test_empty(self) -> None:
        assert group_by([], key_fn=lambda x: x) == {}

    def test_single_group(self) -> None:
        result = group_by([1, 2, 3], key_fn=lambda _: "all")
        assert result == {"all": [1, 2, 3]}
