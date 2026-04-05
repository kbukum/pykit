"""Directed acyclic graph of nodes."""

from __future__ import annotations

from pykit_dag.node import Node
from pykit_errors import AppError
from pykit_errors.codes import ErrorCode


class CycleError(AppError):
    """Raised when a cycle is detected in the graph."""

    def __init__(self, message: str = "cycle detected in graph") -> None:
        super().__init__(ErrorCode.INVALID_INPUT, message)


class MissingNodeError(AppError):
    """Raised when an edge references a node not in the graph."""

    def __init__(self, node_name: str) -> None:
        super().__init__(ErrorCode.NOT_FOUND, f"node '{node_name}' not found in graph")


class Graph:
    """A directed acyclic graph of nodes with edges."""

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._edges: dict[str, set[str]] = {}  # from -> {to, ...}
        self._reverse: dict[str, set[str]] = {}  # to -> {from, ...}

    @property
    def nodes(self) -> dict[str, Node]:
        return dict(self._nodes)

    def add_node(self, node: Node) -> None:
        """Add a node to the graph."""
        self._nodes[node.name] = node
        self._edges.setdefault(node.name, set())
        self._reverse.setdefault(node.name, set())

    def add_edge(self, from_name: str, to_name: str) -> None:
        """Add a directed edge from one node to another."""
        for name in (from_name, to_name):
            if name not in self._nodes:
                raise MissingNodeError(name)
        self._edges[from_name].add(to_name)
        self._reverse[to_name].add(from_name)

    def validate(self) -> None:
        """Validate the graph: check for cycles and missing dependencies."""
        # Check that all declared dependencies exist
        for node in self._nodes.values():
            for dep in node.dependencies:
                if dep not in self._nodes:
                    raise MissingNodeError(dep)

        # Detect cycles via DFS
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {name: WHITE for name in self._nodes}

        def dfs(name: str) -> None:
            color[name] = GRAY
            for neighbor in self._edges.get(name, set()):
                if color[neighbor] == GRAY:
                    raise CycleError(f"cycle detected: edge {name} -> {neighbor}")
                if color[neighbor] == WHITE:
                    dfs(neighbor)
            # Also follow declared dependencies (reverse direction for cycle check)
            node = self._nodes[name]
            for dep in node.dependencies:
                if dep in self._nodes:
                    # dep -> name is the logical edge; check dep hasn't created a cycle
                    pass
            color[name] = BLACK

        for name in self._nodes:
            if color[name] == WHITE:
                dfs(name)

    def topological_sort(self) -> list[list[str]]:
        """Return nodes grouped by execution level for parallel execution.

        Nodes in the same level have no dependencies on each other
        and can run concurrently.
        """
        self.validate()

        # Build effective in-degree using both explicit edges and declared dependencies
        in_degree: dict[str, int] = {name: 0 for name in self._nodes}
        adj: dict[str, set[str]] = {name: set() for name in self._nodes}

        # Explicit edges
        for src, targets in self._edges.items():
            for tgt in targets:
                adj[src].add(tgt)
                in_degree[tgt] += 1

        # Declared dependencies: dep -> node (dep must run before node)
        for node in self._nodes.values():
            for dep in node.dependencies:
                if dep in self._nodes and node.name not in adj.get(dep, set()):
                    adj.setdefault(dep, set()).add(node.name)
                    in_degree[node.name] += 1

        # Kahn's algorithm producing levels
        queue = [name for name, deg in in_degree.items() if deg == 0]
        levels: list[list[str]] = []

        while queue:
            levels.append(sorted(queue))  # sort for deterministic ordering
            next_queue: list[str] = []
            for name in queue:
                for neighbor in adj.get(name, set()):
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_queue.append(neighbor)
            queue = next_queue

        processed = sum(len(level) for level in levels)
        if processed != len(self._nodes):
            raise CycleError("cycle detected in graph")

        return levels
