"""Path planning for Raven (C++ ``navigation/``; chapter 8 "Practical Path Planning").

- :class:`PathPlanner`: one per bot. Finds the closest reachable graph node, and requests
  searches to a position (A*) or to the closest active item of a type (Dijkstra with a
  termination condition).
- :class:`PathManager`: one per game. Runs every pending search a few cycles per update, so
  path planning never stalls a frame (time slicing). A cycle is one step of the search
  generators in ``gameai.common.graph_search``.
- Paths are lists of :class:`PathEdge` that keep each edge's traversal flags (e.g. going
  through a door). They can be smoothed quickly or precisely.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field, replace
from enum import Enum, auto
from typing import TYPE_CHECKING

from gameai.common.graph import EdgeBehavior, GraphEdge
from gameai.common.graph_search import AStarSearch, DijkstraSearch, euclidean
from gameai.common.messaging import SENDER_IRRELEVANT
from gameai.common.vector2d import Vector2D
from gameai.raven.entity_types import EntityType, Message

if TYPE_CHECKING:
    from gameai.raven.bot import RavenBot
    from gameai.raven.map import NavGraph


@dataclass(frozen=True)
class PathEdge:
    source: Vector2D
    destination: Vector2D
    behavior: EdgeBehavior = EdgeBehavior.NORMAL
    door_id: int = -1


class SearchStatus(Enum):
    INCOMPLETE = auto()
    FOUND = auto()
    NOT_FOUND = auto()


type CanWalkBetween = Callable[[Vector2D, Vector2D], bool]


def _mergeable(first: PathEdge, second: PathEdge, can_walk_between: CanWalkBetween) -> bool:
    """Two edges can become one if both are plain walking and the shortcut is clear.

    The C++ code only checks the second edge's flags, so it could stretch a door edge past
    the door.
    """
    return (
        first.behavior is EdgeBehavior.NORMAL
        and second.behavior is EdgeBehavior.NORMAL
        and can_walk_between(first.source, second.destination)
    )


# --- paths ----------------------------------------------------------------------------------------
def path_as_edges(graph: NavGraph, nodes: list[int]) -> list[PathEdge]:
    """Turn a node path into edges annotated with the graph edges' flags."""
    edges = []
    for a, b in itertools.pairwise(nodes):
        edge = graph.edge(a, b)
        edges.append(
            PathEdge(
                graph.node(a).position,
                graph.node(b).position,
                edge.flags,
                edge.intersecting_entity,
            )
        )
    return edges


def smooth_quick(path: list[PathEdge], can_walk_between: CanWalkBetween) -> list[PathEdge]:
    """Merge each edge into the previous one while the bot can walk straight across both.

    Fast, but only looks one edge ahead (``SmoothPathEdgesQuick``).
    """
    if not path:
        return []
    smoothed = [path[0]]
    for edge in path[1:]:
        last = smoothed[-1]
        if _mergeable(last, edge, can_walk_between):
            smoothed[-1] = replace(last, destination=edge.destination)
        else:
            smoothed.append(edge)
    return smoothed


def smooth_precise(path: list[PathEdge], can_walk_between: CanWalkBetween) -> list[PathEdge]:
    """From each edge, jump to the *furthest* later edge reachable in a straight line.

    Slower than ``smooth_quick`` but removes more kinks (``SmoothPathEdgesPrecise``).
    """
    smoothed: list[PathEdge] = []
    i = 0
    while i < len(path):
        start = path[i]
        furthest = i
        for j in range(i + 1, len(path)):
            if path[j].behavior is not EdgeBehavior.NORMAL:
                break  # never shortcut across a door (or any special edge)
            if _mergeable(start, path[j], can_walk_between):
                furthest = j
        smoothed.append(replace(start, destination=path[furthest].destination))
        i = furthest + 1
    return smoothed


# --- the path planner ---------------------------------------------------------------------------
class NoSearchError(Exception):
    """Raised by :meth:`PathPlanner.cycle_once` when nothing is being searched for."""


@dataclass(eq=False)
class PathPlanner:
    bot: RavenBot
    destination: Vector2D = field(default_factory=Vector2D, init=False)
    search: AStarSearch | None = field(default=None, init=False)
    _steps: Iterator[GraphEdge] | None = field(default=None, init=False)
    smoothing: Callable[[list[PathEdge], CanWalkBetween], list[PathEdge]] | None = None

    @property
    def graph(self) -> NavGraph:
        return self.bot.world.map.graph

    def _get_ready_for_new_search(self) -> None:
        self.bot.world.path_manager.unregister(self)
        self.search, self._steps = None, None

    def closest_node_to(self, position: Vector2D) -> int | None:
        """The closest graph node the bot could walk to in a straight line from ``position``."""
        game_map = self.bot.world.map
        candidates = game_map.cell_space.neighbors(position, game_map.cell_space_neighborhood_range)
        reachable = [n for n in candidates if self.bot.can_walk_between(position, n.position)]
        closest = min(reachable, key=lambda n: n.position.distance_sq(position), default=None)
        return None if closest is None else closest.index

    def request_path_to_position(self, target: Vector2D) -> bool:
        """Start an A* search to ``target``; False if either end is off the graph.

        If the target can be walked to directly no search is needed: the path will be the
        single edge from the bot to the target (the C++ version leaves that to the caller).
        """
        self._get_ready_for_new_search()
        self.destination = target
        if self.bot.can_walk_to(target):
            return True
        start, end = self.closest_node_to(self.bot.position), self.closest_node_to(target)
        if start is None or end is None:
            return False
        self._start(AStarSearch(self.graph, start, end, euclidean))
        return True

    def request_path_to_item(self, item_type: EntityType) -> bool:
        """Start a Dijkstra search for the closest active item of this type."""
        self._get_ready_for_new_search()
        start = self.closest_node_to(self.bot.position)
        if start is None:
            return False

        def is_active_item(node: int) -> bool:
            item = self.graph.node(node).extra
            return item is not None and item.active and item.entity_type is item_type

        self._start(DijkstraSearch(self.graph, start, is_target=is_active_item))
        return True

    def _start(self, search: AStarSearch) -> None:
        self.search, self._steps = search, search.steps()
        self.bot.world.path_manager.register(self)

    @property
    def is_direct(self) -> bool:
        """True after a position request that needs no search (walkable in a straight line)."""
        return self.search is None

    def cycle_once(self) -> SearchStatus:
        """Advance the search one step; tell the bot when it finishes (``CycleOnce``)."""
        if self.search is None or self._steps is None:
            raise NoSearchError
        if next(self._steps, None) is not None:
            return SearchStatus.INCOMPLETE
        dispatcher, bot_id = self.bot.world.dispatcher, self.bot.id
        if not self.search.found:
            dispatcher.dispatch(Message.NO_PATH_AVAILABLE, SENDER_IRRELEVANT, bot_id)
            return SearchStatus.NOT_FOUND
        assert self.search.target is not None
        item = self.graph.node(self.search.target).extra  # the item found, for item searches
        dispatcher.dispatch(Message.PATH_READY, SENDER_IRRELEVANT, bot_id, extra=item)
        return SearchStatus.FOUND

    def path(self) -> list[PathEdge]:
        """The found path: bot → first node → ... → last node (→ destination, for positions)."""
        position = self.bot.position
        if self.search is None:  # direct: no graph needed
            return [PathEdge(position, self.destination)]
        nodes = self.search.path_to_target()
        edges = path_as_edges(self.graph, nodes)
        edges.insert(0, PathEdge(position, self.graph.node(nodes[0]).position))
        if self.search.is_target is None:  # a search to a position, not an item
            edges.append(PathEdge(edges[-1].destination, self.destination))
        if self.smoothing is not None:
            edges = self.smoothing(edges, self.bot.can_walk_between)
        return edges

    def cost_to_node(self, node: int) -> float:
        """Estimated cost from the bot to ``node``, using the precalculated cost table."""
        start = self.closest_node_to(self.bot.position)
        if start is None:
            return math.inf
        game_map = self.bot.world.map
        return (
            self.bot.position.distance(self.graph.node(start).position)
            + (game_map.path_costs[start][node])
        )

    def cost_to_closest_item(self, item_type: EntityType) -> float | None:
        """Cost to the nearest active item of the type, or None if there is none."""
        start = self.closest_node_to(self.bot.position)
        if start is None:
            return None
        costs = self.bot.world.map.path_costs[start]
        return min(
            (
                costs[item.graph_node_index]
                for item in self.bot.world.map.items()
                if item.active and item.entity_type is item_type
            ),
            default=None,
        )


@dataclass
class PathManager:
    """Shares a fixed number of search cycles per update between all pending searches."""

    cycles_per_update: int
    requests: list[PathPlanner] = field(default_factory=list)

    def register(self, planner: PathPlanner) -> None:
        if planner not in self.requests:
            self.requests.append(planner)

    def unregister(self, planner: PathPlanner) -> None:
        if planner in self.requests:
            self.requests.remove(planner)

    def update_searches(self) -> None:
        """Round-robin one cycle at a time until the budget runs out or all searches end."""
        budget, index = self.cycles_per_update, 0
        while budget > 0 and self.requests:
            budget -= 1
            index %= len(self.requests)
            planner = self.requests[index]
            if planner.cycle_once() is SearchStatus.INCOMPLETE:
                index += 1
            else:
                self.requests.pop(index)
