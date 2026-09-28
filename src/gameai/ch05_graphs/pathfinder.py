"""The Pathfinder tool (C++ ``Pathfinder``): a terrain grid, its navigation graph and searches."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from pathlib import Path

from gameai.common.graph import (
    GraphEdge,
    NavGraphNode,
    SparseGraph,
    add_all_neighbours_to_grid_node,
    create_grid,
    weight_node_edges,
)
from gameai.common.graph_search import (
    AStarSearch,
    BreadthFirstSearch,
    DepthFirstSearch,
    DijkstraSearch,
    GraphSearch,
    euclidean,
)
from gameai.common.vector2d import Vector2D


class Terrain(IntEnum):
    """Cell types; the values are the ones stored in ``.map`` files."""

    NORMAL = 0
    OBSTACLE = 1
    WATER = 2
    MUD = 3
    SOURCE = 4  # only in files: marks the source cell
    TARGET = 5  # only in files: marks the target cell


TERRAIN_COST = {Terrain.NORMAL: 1.0, Terrain.WATER: 2.0, Terrain.MUD: 1.5}


class Algorithm(Enum):
    DFS = "Depth first"
    BFS = "Breadth first"
    DIJKSTRA = "Dijkstra"
    ASTAR = "A*"


@dataclass(eq=False)
class Pathfinder:
    cells_x: int
    cells_y: int
    width: float
    height: float
    terrain: list[Terrain] = field(init=False)
    graph: SparseGraph[NavGraphNode, GraphEdge] = field(init=False)
    source: int = field(init=False)
    target: int = field(init=False)
    algorithm: Algorithm | None = field(default=None, init=False)
    search: GraphSearch | None = field(default=None, init=False)
    time_taken: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        self.terrain = [Terrain.NORMAL] * (self.cells_x * self.cells_y)
        self.graph = create_grid(self.width, self.height, self.cells_x, self.cells_y)
        middle = self.cells_x // 2
        self.target = 2 * self.cells_x + middle  # near the top, as in the C++ default
        self.source = (self.cells_y - 3) * self.cells_x + middle  # near the bottom

    @property
    def cell_width(self) -> float:
        return self.width / self.cells_x

    @property
    def cell_height(self) -> float:
        return self.height / self.cells_y

    def cell_at(self, pos: Vector2D) -> int | None:
        """The cell under ``pos`` (y up, row 0 at the top), or None if outside the grid."""
        col, row = int(pos.x // self.cell_width), int((self.height - pos.y) // self.cell_height)
        if 0 <= col < self.cells_x and 0 <= row < self.cells_y:
            return row * self.cells_x + col
        return None

    def cell_center(self, cell: int) -> Vector2D:
        row, col = divmod(cell, self.cells_x)
        return Vector2D((col + 0.5) * self.cell_width, self.height - (row + 0.5) * self.cell_height)

    # --- editing ----------------------------------------------------------------------------
    def paint(self, cell: int, brush: Terrain) -> None:
        """Apply a brush to a cell and rerun the current search (``PaintTerrain``)."""
        if brush is Terrain.SOURCE:
            self.source = cell
        elif brush is Terrain.TARGET:
            self.target = cell
        else:
            self.set_terrain(cell, brush)
        if self.algorithm is not None:
            self.run(self.algorithm)

    def set_terrain(self, cell: int, terrain: Terrain) -> None:
        """Obstacles remove the node; other terrains (re)add it and weight its edges."""
        self.terrain[cell] = terrain
        if terrain is Terrain.OBSTACLE:
            if self.graph.is_node_present(cell):
                self.graph.remove_node(cell)
            return
        if not self.graph.is_node_present(cell):
            self.graph.add_node(NavGraphNode(cell, self.cell_center(cell)))
            row, col = divmod(cell, self.cells_x)
            add_all_neighbours_to_grid_node(self.graph, row, col, self.cells_x, self.cells_y)
        weight_node_edges(self.graph, cell, TERRAIN_COST[terrain])

    # --- searching --------------------------------------------------------------------------
    def make_search(self, algorithm: Algorithm) -> GraphSearch:
        """A search from source to target, not yet run (so its steps can be animated)."""
        self.algorithm = algorithm
        if not (
            self.graph.is_node_present(self.source) and self.graph.is_node_present(self.target)
        ):
            self.search = None
            return GraphSearch(self.graph, self.source, self.target)
        match algorithm:
            case Algorithm.DFS:
                self.search = DepthFirstSearch(self.graph, self.source, self.target)
            case Algorithm.BFS:
                self.search = BreadthFirstSearch(self.graph, self.source, self.target)
            case Algorithm.DIJKSTRA:
                self.search = DijkstraSearch(self.graph, self.source, self.target)
            case Algorithm.ASTAR:
                self.search = AStarSearch(self.graph, self.source, self.target, euclidean)
        return self.search

    def run(self, algorithm: Algorithm) -> GraphSearch:
        search = self.make_search(algorithm)
        start = time.perf_counter()
        if self.search is not None:
            search.run()
        self.time_taken = time.perf_counter() - start
        return search

    # --- files (Pathfinder::Save / Load) -------------------------------------------------------
    def save(self, path: Path) -> None:
        cells = [
            Terrain.SOURCE if i == self.source else Terrain.TARGET if i == self.target else t
            for i, t in enumerate(self.terrain)
        ]
        path.write_text("\n".join(map(str, [self.cells_x, self.cells_y, *map(int, cells)])) + "\n")

    @classmethod
    def load(cls, path: Path, width: float, height: float) -> Pathfinder:
        numbers = [int(token) for token in path.read_text().split()]
        cells_x, cells_y, *cells = numbers
        pathfinder = cls(cells_x, cells_y, width, height)
        for cell, value in enumerate(cells[: cells_x * cells_y]):
            match Terrain(value):
                case Terrain.SOURCE:
                    pathfinder.source = cell
                case Terrain.TARGET:
                    pathfinder.target = cell
                case terrain:
                    if terrain is not Terrain.NORMAL:
                        pathfinder.set_terrain(cell, terrain)
        return pathfinder
