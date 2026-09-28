"""Graph search algorithms (C++ ``Common/Graph/GraphAlgorithms.h``, ``AStarHeuristicPolicies.h``).

Each search is a class whose :meth:`GraphSearch.steps` generator advances the search one
step at a time, yielding the edge it just added to the search tree. Running it to the end
(:meth:`GraphSearch.run`) gives the same result as the C++ constructors, while iterating
the steps lets a demo animate the search or a game spread it over several frames (the
time-sliced searches of chapter 8).
"""

from __future__ import annotations

import heapq
import itertools
import math
import random
from collections import deque
from collections.abc import Callable, Iterator
from typing import Any, Self

from gameai.common.graph import GraphEdge, NavGraphNode, SparseGraph

type Graph = SparseGraph[NavGraphNode, Any]
type Heuristic = Callable[[Graph, int, int], float]


class GraphSearch:
    """Common state: the search tree, the parent of each reached node and the outcome."""

    name = "search"

    def __init__(self, graph: Graph, source: int, target: int | None = None) -> None:
        self.graph, self.source, self.target = graph, source, target
        self.tree: list[GraphEdge] = []  # edges in the order they joined the search tree
        self.parent: dict[int, int] = {}
        self.found = False
        self.done = False

    def steps(self) -> Iterator[GraphEdge]:
        raise NotImplementedError

    def run(self) -> Self:
        for _ in self.steps():
            pass
        return self

    def path_to_target(self) -> list[int]:
        """Node indices from source to target, or [] if the target wasn't reached."""
        if not self.found or self.target is None:
            return []
        path, node = [self.target], self.target
        while node != self.source:
            node = self.parent[node]
            path.append(node)
        return path[::-1]

    @property
    def cost_to_target(self) -> float:
        path = self.path_to_target()
        return float(sum(self.graph.edge(a, b).cost for a, b in itertools.pairwise(path)))


class DepthFirstSearch(GraphSearch):
    """Go as deep as possible first, using a stack (``Graph_SearchDFS``)."""

    name = "Depth first"

    def steps(self) -> Iterator[GraphEdge]:
        visited: set[int] = set()
        stack = [GraphEdge(self.source, self.source, 0)]  # dummy edge into the source
        while stack:
            edge = stack.pop()
            if edge.to_index in visited:
                continue
            visited.add(edge.to_index)
            self.parent[edge.to_index] = edge.from_index
            if edge.to_index != self.source:
                self.tree.append(edge)
                yield edge
            if edge.to_index == self.target:
                self.found = True
                break
            stack.extend(
                e for e in self.graph.edges_from(edge.to_index) if e.to_index not in visited
            )
        self.done = True


class BreadthFirstSearch(GraphSearch):
    """Fan out level by level, using a queue: fewest edges, ignoring costs (``Graph_SearchBFS``)."""

    name = "Breadth first"

    def steps(self) -> Iterator[GraphEdge]:
        visited = {self.source}
        queue = deque([GraphEdge(self.source, self.source, 0)])
        while queue:
            edge = queue.popleft()
            self.parent[edge.to_index] = edge.from_index
            if edge.to_index != self.source:
                self.tree.append(edge)
                yield edge
            if edge.to_index == self.target:
                self.found = True
                break
            for e in self.graph.edges_from(edge.to_index):
                if e.to_index not in visited:
                    visited.add(e.to_index)  # mark when queued, so each node is queued once
                    queue.append(e)
        self.done = True


# --- heuristics (AStarHeuristicPolicies.h) ------------------------------------------------
def euclidean(graph: Graph, a: int, b: int) -> float:
    return graph.node(a).position.distance(graph.node(b).position)


def manhattan(graph: Graph, a: int, b: int) -> float:
    pa, pb = graph.node(a).position, graph.node(b).position
    return abs(pa.x - pb.x) + abs(pa.y - pb.y)


def noisy_euclidean(rng: random.Random | None = None) -> Heuristic:
    """Euclidean distance scaled by a random factor in [0.9, 1.1]: less predictable paths."""
    r = rng or random.Random()
    return lambda graph, a, b: euclidean(graph, a, b) * r.uniform(0.9, 1.1)


def zero(graph: Graph, a: int, b: int) -> float:
    return 0.0


class AStarSearch(GraphSearch):
    """Expand the node with the lowest cost so far + estimated cost to go (``Graph_SearchAStar``).

    The C++ code uses an indexed priority queue whose priorities can be lowered in place. With
    ``heapq`` the usual Python approach is to push a new entry when a node's cost improves and
    skip stale entries when they are popped (lazy deletion).
    """

    name = "A*"

    def __init__(
        self,
        graph: Graph,
        source: int,
        target: int | None = None,
        heuristic: Heuristic = euclidean,
        is_target: Callable[[int], bool] | None = None,
    ) -> None:
        super().__init__(graph, source, target)
        self.heuristic = heuristic
        # A termination condition instead of a fixed target: the search stops at the first
        # settled node that satisfies it (C++ ``SearchTerminationPolicies``).
        self.is_target = is_target
        self.g_cost: dict[int, float] = {source: 0.0}  # best known cost from the source
        self.frontier: dict[int, GraphEdge] = {}  # best edge found so far into each node
        self.shortest_path_tree: dict[int, GraphEdge] = {}  # settled nodes

    def _estimate(self, node: int) -> float:
        return 0.0 if self.target is None else self.heuristic(self.graph, node, self.target)

    def steps(self) -> Iterator[GraphEdge]:
        queue: list[tuple[float, int, int]] = [(self._estimate(self.source), 0, self.source)]
        order = itertools.count(1)
        while queue:
            _, _, node = heapq.heappop(queue)
            if node in self.shortest_path_tree or (
                node != self.source and node not in self.frontier
            ):
                continue  # a stale entry for an already settled node
            if node != self.source:
                edge = self.frontier[node]
                self.shortest_path_tree[node] = edge
                self.parent[node] = edge.from_index
                self.tree.append(edge)
                yield edge
            else:
                self.shortest_path_tree.setdefault(node, GraphEdge(node, node, 0))
            if node == self.target or (self.is_target is not None and self.is_target(node)):
                self.target, self.found = node, True
                break
            for edge in self.graph.edges_from(node):
                to = edge.to_index
                g = self.g_cost[node] + edge.cost
                if to not in self.shortest_path_tree and g < self.g_cost.get(to, math.inf):
                    self.g_cost[to] = g
                    self.frontier[to] = edge
                    heapq.heappush(queue, (g + self._estimate(to), next(order), to))
        self.done = True

    @property
    def cost_to_target(self) -> float:
        return self.g_cost[self.target] if self.found and self.target is not None else 0.0


class DijkstraSearch(AStarSearch):
    """A* with a zero heuristic: expands strictly by cost so far (``Graph_SearchDijkstra``).

    With no target it builds the full shortest path tree from the source.
    """

    name = "Dijkstra"

    def __init__(
        self,
        graph: Graph,
        source: int,
        target: int | None = None,
        is_target: Callable[[int], bool] | None = None,
    ) -> None:
        super().__init__(graph, source, target, heuristic=zero, is_target=is_target)
