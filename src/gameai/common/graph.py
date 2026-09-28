"""Sparse graphs (C++ ``Common/Graph``: ``GraphNodeTypes``, ``GraphEdgeTypes``, ``SparseGraph``,
and the grid helpers from ``HandyGraphFunctions``).

Nodes live in a list indexed by node index; a removed node leaves ``None`` in its slot so
the other indices stay valid (the C++ code marks it ``invalid_node_index``). Each node's
outgoing edges are a dict keyed by destination, so edges are unique and lookups are O(1).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Self

from gameai.common.vector2d import Vector2D


@dataclass
class GraphNode:
    index: int


@dataclass
class NavGraphNode(GraphNode):
    """A node with a position, for navigation graphs. ``extra`` holds game-specific data."""

    position: Vector2D
    extra: Any = None


@dataclass
class GraphEdge:
    from_index: int
    to_index: int
    cost: float = 1.0

    def reversed(self) -> Self:
        return dataclasses.replace(self, from_index=self.to_index, to_index=self.from_index)


class SparseGraph[N: GraphNode, E: GraphEdge]:
    def __init__(self, digraph: bool = False) -> None:
        self.digraph = digraph
        self._nodes: list[N | None] = []
        self._edges: list[dict[int, E]] = []

    # --- nodes ------------------------------------------------------------------------------
    @property
    def next_free_index(self) -> int:
        return len(self._nodes)

    def add_node(self, node: N) -> int:
        """Add ``node`` at ``node.index``: either the next free index or a removed node's slot."""
        if node.index < len(self._nodes):
            if self._nodes[node.index] is not None:
                raise ValueError(f"node {node.index} already exists")
            self._nodes[node.index] = node
        elif node.index == len(self._nodes):
            self._nodes.append(node)
            self._edges.append({})
        else:
            raise ValueError(f"node index {node.index} skips {len(self._nodes)}")
        return node.index

    def remove_node(self, index: int) -> None:
        """Remove a node and every edge touching it."""
        self._nodes[index] = None
        for to_index in list(self._edges[index]):
            self._edges[to_index].pop(index, None)
        self._edges[index].clear()
        if self.digraph:  # edges pointing at the node from nodes it doesn't point at
            for edges in self._edges:
                edges.pop(index, None)

    def node(self, index: int) -> N:
        node = self._nodes[index]
        if node is None:
            raise KeyError(f"node {index} has been removed")
        return node

    def is_node_present(self, index: int) -> bool:
        return 0 <= index < len(self._nodes) and self._nodes[index] is not None

    def __iter__(self) -> Iterator[N]:
        """The active (non-removed) nodes."""
        return (node for node in self._nodes if node is not None)

    @property
    def num_nodes(self) -> int:
        """Size of the node list, including removed slots (search arrays are this big)."""
        return len(self._nodes)

    @property
    def num_active_nodes(self) -> int:
        return sum(1 for _ in self)

    # --- edges ------------------------------------------------------------------------------
    def add_edge(self, edge: E) -> None:
        """Add an edge (and its reverse, for undirected graphs) unless it already exists."""
        if not (self.is_node_present(edge.from_index) and self.is_node_present(edge.to_index)):
            return
        self._edges[edge.from_index].setdefault(edge.to_index, edge)
        if not self.digraph:
            self._edges[edge.to_index].setdefault(edge.from_index, edge.reversed())

    def remove_edge(self, from_index: int, to_index: int) -> None:
        self._edges[from_index].pop(to_index, None)
        if not self.digraph:
            self._edges[to_index].pop(from_index, None)

    def edge(self, from_index: int, to_index: int) -> E:
        return self._edges[from_index][to_index]

    def is_edge_present(self, from_index: int, to_index: int) -> bool:
        return self.is_node_present(from_index) and to_index in self._edges[from_index]

    def edges_from(self, index: int) -> Iterator[E]:
        return iter(self._edges[index].values())

    def all_edges(self) -> Iterator[E]:
        return (edge for edges in self._edges for edge in edges.values())

    def set_edge_cost(self, from_index: int, to_index: int, cost: float) -> None:
        self._edges[from_index][to_index].cost = cost

    @property
    def num_edges(self) -> int:
        return sum(len(edges) for edges in self._edges)

    def clear(self) -> None:
        self._nodes.clear()
        self._edges.clear()


type NavGraph = SparseGraph[NavGraphNode, GraphEdge]


# --- grid helpers (HandyGraphFunctions.h) ------------------------------------------------
def add_all_neighbours_to_grid_node(
    graph: SparseGraph[NavGraphNode, GraphEdge], row: int, col: int, cells_x: int, cells_y: int
) -> None:
    """Connect a grid node to its 8 neighbours, with the distance between them as cost."""
    index = row * cells_x + col
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            x, y = col + dx, row + dy
            if (dx, dy) == (0, 0) or not (0 <= x < cells_x and 0 <= y < cells_y):
                continue
            neighbour = y * cells_x + x
            if not graph.is_node_present(neighbour):
                continue
            cost = graph.node(index).position.distance(graph.node(neighbour).position)
            graph.add_edge(GraphEdge(index, neighbour, cost))


def create_grid(
    width: float, height: float, cells_x: int, cells_y: int
) -> SparseGraph[NavGraphNode, GraphEdge]:
    """A grid navigation graph: node ``row * cells_x + col`` at each cell center.

    Row 0 is the *top* row (as in the C++ map files); positions use a y-up axis.
    """
    graph: SparseGraph[NavGraphNode, GraphEdge] = SparseGraph(digraph=False)
    cell_w, cell_h = width / cells_x, height / cells_y
    for row in range(cells_y):
        for col in range(cells_x):
            center = Vector2D((col + 0.5) * cell_w, height - (row + 0.5) * cell_h)
            graph.add_node(NavGraphNode(graph.next_free_index, center))
    for row in range(cells_y):
        for col in range(cells_x):
            add_all_neighbours_to_grid_node(graph, row, col, cells_x, cells_y)
    return graph


def weight_node_edges(
    graph: SparseGraph[NavGraphNode, GraphEdge], index: int, weight: float
) -> None:
    """Set the cost of every edge touching ``index`` to its length times ``weight``."""
    for edge in list(graph.edges_from(index)):
        start, end = graph.node(edge.from_index), graph.node(edge.to_index)
        cost = start.position.distance(end.position) * weight
        graph.set_edge_cost(edge.from_index, edge.to_index, cost)
        if not graph.digraph:
            graph.set_edge_cost(edge.to_index, edge.from_index, cost)
