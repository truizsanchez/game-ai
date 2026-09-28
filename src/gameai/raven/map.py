"""The Raven map (C++ ``Raven_Map``): navigation graph, walls, doors, items and spawn points.

Map files use a y-down screen; everything is converted to the y-up axis on load
(``y → size_y - y``). Entity ids are taken from the file, because edges and switches refer
to them (a door's id is stored on the navigation edges that go through it).
"""

from __future__ import annotations

import random
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from gameai.common.cell_space import CellSpacePartition
from gameai.common.geometry import Wall2D
from gameai.common.graph import EdgeBehavior, NavGraphEdge, NavGraphNode, SparseGraph
from gameai.common.graph_search import DijkstraSearch
from gameai.common.messaging import EntityRegistry, MessageDispatcher, Receiver
from gameai.common.triggers import CircleRegion, RectangleRegion, TriggerSystem
from gameai.common.vector2d import Vector2D
from gameai.raven.entity_types import EntityType, Message
from gameai.raven.items import ButtonSendMessage, HealthGiver, RavenDoor, WeaponGiver
from gameai.raven.params import Params

if TYPE_CHECKING:
    from gameai.raven.bot import RavenBot

type NavGraph = SparseGraph[NavGraphNode, NavGraphEdge]


@dataclass(eq=False)
class RavenMap:
    size_x: float
    size_y: float
    graph: NavGraph
    walls: list[Wall2D] = field(default_factory=list)
    doors: list[RavenDoor] = field(default_factory=list)
    spawn_points: list[Vector2D] = field(default_factory=list)
    triggers: TriggerSystem[RavenBot] = field(default_factory=TriggerSystem)
    max_entity_id: int = -1
    cell_space: CellSpacePartition[NavGraphNode] = field(init=False)

    @property
    def cell_space_neighborhood_range(self) -> float:
        """Average edge length + 1: a search radius that finds at least one nearby node."""
        edges = list(self.graph.all_edges())
        return (sum(e.cost for e in edges) / len(edges) if edges else 0) + 1

    @cached_property
    def path_costs(self) -> list[list[float]]:
        """Cost of the cheapest path between every pair of nodes (``CreateAllPairsCostsTable``)."""
        n = self.graph.num_nodes
        table = [[0.0] * n for _ in range(n)]
        for node in self.graph:
            search = DijkstraSearch(self.graph, node.index).run()
            for target, cost in search.g_cost.items():
                table[node.index][target] = cost
        return table

    def random_node_position(self, rng: random.Random) -> Vector2D:
        return rng.choice(list(self.graph)).position

    def random_spawn_point(self, rng: random.Random) -> Vector2D:
        return rng.choice(self.spawn_points)

    def update_doors(self) -> None:
        for door in self.doors:
            door.update()

    # --- loading -------------------------------------------------------------------------------
    @classmethod
    def load(
        cls,
        path: Path,
        params: Params,
        dispatcher: MessageDispatcher,
        entities: EntityRegistry[Receiver],
    ) -> RavenMap:
        tokens = _Tokens(path.read_text().split())
        graph = _read_graph(tokens)
        size_x, size_y = tokens.number(), tokens.number()
        flip = _Flip(size_y)
        for node in graph:
            node.position = flip.point(node.position)
        game_map = cls(size_x, size_y, graph)
        game_map.cell_space = CellSpacePartition(
            size_x, size_y, params.num_cells_x, params.num_cells_y
        )
        for node in graph:
            game_map.cell_space.add(node)

        giver_range = params.items.default_giver_trigger_range
        while tokens:
            kind = EntityType(int(tokens.number()))
            match kind:
                case EntityType.WALL:
                    game_map.walls.append(flip.wall(tokens.points(3)))
                    continue
                case _:
                    entity_id = int(tokens.number())
                    game_map.max_entity_id = max(game_map.max_entity_id, entity_id)
            match kind:
                case EntityType.SLIDING_DOOR:
                    p1, p2 = (flip.point(p) for p in tokens.points(2))
                    switches = [int(tokens.number()) for _ in range(int(tokens.number()))]
                    door = RavenDoor(
                        id=entity_id, p1=p1, p2=p2, switch_ids=switches, walls=game_map.walls
                    )
                    game_map.doors.append(door)
                    entities.register(door)
                case EntityType.DOOR_TRIGGER:
                    receiver, message = int(tokens.number()), Message(int(tokens.number()))
                    [center], radius = [flip.point(p) for p in tokens.points(1)], tokens.number()
                    corner = Vector2D(radius, radius)
                    button = ButtonSendMessage(
                        center,
                        radius,
                        id=entity_id,
                        region=RectangleRegion(center - corner, center + corner),
                        receiver=receiver,
                        message=message,
                        dispatcher=dispatcher,
                    )
                    game_map.triggers.register(button)
                    entities.register(button)
                case EntityType.SPAWN_POINT:
                    [position] = [flip.point(p) for p in tokens.points(1)]
                    tokens.number(), tokens.number()  # radius and node: map editor leftovers
                    game_map.spawn_points.append(position)
                case EntityType.HEALTH:
                    [center] = [flip.point(p) for p in tokens.points(1)]
                    radius, health = tokens.number(), int(tokens.number())
                    node_index = int(tokens.number())
                    giver = HealthGiver(
                        center,
                        radius,
                        id=entity_id,
                        region=CircleRegion(center, giver_range),
                        graph_node_index=node_index,
                        respawn_delay=params.seconds_to_ticks(params.items.health_respawn_delay),
                        health_given=health,
                    )
                    game_map._add_item(giver, entities)
                case EntityType.SHOTGUN | EntityType.RAIL_GUN | EntityType.ROCKET_LAUNCHER:
                    [center] = [flip.point(p) for p in tokens.points(1)]
                    radius, node_index = tokens.number(), int(tokens.number())
                    weapon = WeaponGiver(
                        center,
                        radius,
                        id=entity_id,
                        region=CircleRegion(center, giver_range),
                        graph_node_index=node_index,
                        respawn_delay=params.seconds_to_ticks(params.items.weapon_respawn_delay),
                        entity_type=kind,
                    )
                    game_map._add_item(weapon, entities)
                case _:
                    raise ValueError(f"{path.name}: unexpected object type {kind!r}")
        return game_map

    def _add_item(
        self, item: HealthGiver | WeaponGiver, entities: EntityRegistry[Receiver]
    ) -> None:
        """Register an item trigger and attach it to its graph node (for item searches)."""
        self.triggers.register(item)
        self.graph.node(item.graph_node_index).extra = item
        entities.register(item)  # type: ignore[arg-type]

    def items(self) -> Iterator[HealthGiver | WeaponGiver]:
        for trigger in self.triggers.triggers:
            if isinstance(trigger, HealthGiver | WeaponGiver):
                yield trigger


# --- file parsing helpers ------------------------------------------------------------------
class _Tokens:
    def __init__(self, tokens: list[str]) -> None:
        self._tokens = tokens
        self._index = 0

    def __bool__(self) -> bool:
        return self._index < len(self._tokens)

    def next(self) -> str:
        token = self._tokens[self._index]
        self._index += 1
        return token

    def number(self) -> float:
        return float(self.next())

    def labelled(self) -> float:
        """Skip a ``Label:`` token and return the number after it."""
        self.next()
        return self.number()

    def points(self, count: int) -> list[Vector2D]:
        return [Vector2D(self.number(), self.number()) for _ in range(count)]


def _read_graph(tokens: _Tokens) -> NavGraph:
    """``SparseGraph::Load``: node count, ``Index: i PosX: x PosY: y`` lines, edge count, edges."""
    graph: NavGraph = SparseGraph(digraph=False)
    for _ in range(int(tokens.number())):
        index = int(tokens.labelled())
        position = Vector2D(tokens.labelled(), tokens.labelled())
        if index < 0:
            graph.add_removed_slot()
        else:
            graph.add_node(NavGraphNode(index, position))
    for _ in range(int(tokens.number())):
        start, end, cost = int(tokens.labelled()), int(tokens.labelled()), tokens.labelled()
        flags, entity = int(tokens.labelled()), int(tokens.labelled())
        graph.add_edge(NavGraphEdge(start, end, cost, EdgeBehavior(flags), entity))
    return graph


@dataclass(frozen=True)
class _Flip:
    """Convert from the files' y-down coordinates to y-up."""

    size_y: float

    def point(self, p: Vector2D) -> Vector2D:
        return Vector2D(p.x, self.size_y - p.y)

    def wall(self, values: list[Vector2D]) -> Wall2D:
        """A wall ``start end normal``, oriented so its computed normal matches the file's."""
        start, end, normal = self.point(values[0]), self.point(values[1]), values[2]
        wall = Wall2D(start, end)
        if wall.normal.dot(Vector2D(normal.x, -normal.y)) < 0:
            wall = Wall2D(end, start)
        return wall
