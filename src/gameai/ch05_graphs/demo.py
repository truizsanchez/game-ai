"""The Pathfinder tool in a window. Run with ``python -m gameai.ch05_graphs``."""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from typing import ClassVar, override

import arcade

from gameai.ch05_graphs.pathfinder import Algorithm, Pathfinder, Terrain
from gameai.common.graph import GraphEdge
from gameai.common.sources import original_file
from gameai.common.vector2d import Vector2D
from gameai.common.view import HEIGHT, WIDTH, Color, Demo, draw_circle, draw_line

GRID_SIZE = 520
OFFSET = Vector2D(WIDTH - GRID_SIZE - 20, (HEIGHT - GRID_SIZE) / 2 + 10)
CELLS = 19
MAPS = ("test_with_walls.map", "no_obstacles_source_target_close.map")
TERRAIN_COLORS: dict[Terrain, Color] = {
    Terrain.NORMAL: (235, 235, 235),
    Terrain.OBSTACLE: (60, 60, 60),
    Terrain.WATER: (90, 150, 230),
    Terrain.MUD: (150, 110, 60),
}
STEPS_PER_TICK = 1


class PathfinderDemo(Demo):
    title = "Pathfinder"
    help = (
        "Paint (click/drag):",
        " X obstacle  W water",
        " M mud  E normal",
        " S source  T target",
        "Search:",
        " F DFS  B BFS",
        " D Dijkstra  A A*",
        "Space: animate search",
        "G: graph  C: clear",
        "L: load original map",
    )
    BRUSHES: ClassVar[dict[int, Terrain]] = {
        arcade.key.X: Terrain.OBSTACLE,
        arcade.key.W: Terrain.WATER,
        arcade.key.M: Terrain.MUD,
        arcade.key.E: Terrain.NORMAL,
        arcade.key.S: Terrain.SOURCE,
        arcade.key.T: Terrain.TARGET,
    }
    ALGORITHMS: ClassVar[dict[int, Algorithm]] = {
        arcade.key.F: Algorithm.DFS,
        arcade.key.B: Algorithm.BFS,
        arcade.key.D: Algorithm.DIJKSTRA,
        arcade.key.A: Algorithm.ASTAR,
    }

    def __init__(self) -> None:
        super().__init__()
        self.map_index = -1
        self.pathfinder = Pathfinder(CELLS, CELLS, GRID_SIZE, GRID_SIZE)
        self.brush = Terrain.OBSTACLE
        self.show_graph = False
        self.animation: Iterator[GraphEdge] | None = None
        self.pathfinder.run(Algorithm.ASTAR)

    # --- input ---------------------------------------------------------------------------------
    def on_key_press(self, symbol: int, modifiers: int) -> bool | None:
        pf = self.pathfinder
        if symbol in self.BRUSHES:
            self.brush = self.BRUSHES[symbol]
        elif symbol in self.ALGORITHMS:
            self.animation = None
            pf.run(self.ALGORITHMS[symbol])
        elif symbol == arcade.key.SPACE:
            search = pf.make_search(pf.algorithm or Algorithm.ASTAR)
            self.animation = search.steps() if pf.search is not None else None
        elif symbol == arcade.key.G:
            self.show_graph = not self.show_graph
        elif symbol == arcade.key.C:
            self.replace(Pathfinder(CELLS, CELLS, GRID_SIZE, GRID_SIZE))
        elif symbol == arcade.key.L:
            self.load_next_map()
        else:
            return super().on_key_press(symbol, modifiers)
        return True

    def replace(self, pathfinder: Pathfinder) -> None:
        algorithm = self.pathfinder.algorithm or Algorithm.ASTAR
        self.pathfinder, self.animation = pathfinder, None
        pathfinder.run(algorithm)

    def load_next_map(self) -> None:
        self.map_index = (self.map_index + 1) % len(MAPS)
        path = original_file("Buckland_Chapter5-Pathfinder", MAPS[self.map_index])
        if path is None:
            self.status = "original maps not found (set GAMEAI_ORIGINAL_SOURCE)"
            return
        self.replace(Pathfinder.load(path, GRID_SIZE, GRID_SIZE))

    def paint_at(self, x: float, y: float) -> None:
        cell = self.pathfinder.cell_at(Vector2D(x, y) - OFFSET)
        if cell is not None:
            self.animation = None
            self.pathfinder.paint(cell, self.brush)

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> None:
        self.paint_at(x, y)

    @override
    def on_mouse_drag(self, x: int, y: int, dx: int, dy: int, buttons: int, modifiers: int) -> None:
        if self.brush not in (Terrain.SOURCE, Terrain.TARGET):
            self.paint_at(x, y)

    def step(self, dt: float) -> None:
        if self.animation is None:
            return
        for _ in range(STEPS_PER_TICK):
            if next(self.animation, None) is None:
                self.animation = None  # the search has finished
                break

    # --- drawing -------------------------------------------------------------------------------
    def draw(self) -> None:
        pf = self.pathfinder
        w, h = pf.cell_width, pf.cell_height
        for cell, terrain in enumerate(pf.terrain):
            center = OFFSET + pf.cell_center(cell)
            arcade.draw_lbwh_rectangle_filled(
                center.x - w / 2, center.y - h / 2, w - 1, h - 1, TERRAIN_COLORS[terrain]
            )
        if self.show_graph:
            for edge in pf.graph.all_edges():
                a, b = pf.graph.node(edge.from_index), pf.graph.node(edge.to_index)
                draw_line(OFFSET + a.position, OFFSET + b.position, (180, 180, 180))
        search = pf.search
        if search is not None:
            for edge in search.tree:
                a, b = pf.graph.node(edge.from_index), pf.graph.node(edge.to_index)
                draw_line(OFFSET + a.position, OFFSET + b.position, arcade.color.RED)
            path = search.path_to_target() if search.done else []
            for a_index, b_index in itertools.pairwise(path):
                a, b = pf.graph.node(a_index), pf.graph.node(b_index)
                draw_line(OFFSET + a.position, OFFSET + b.position, arcade.color.BLUE, 4)
        draw_circle(OFFSET + pf.cell_center(pf.source), w * 0.35, arcade.color.GREEN)
        draw_circle(OFFSET + pf.cell_center(pf.target), w * 0.35, arcade.color.RED)
        draw_circle(OFFSET + pf.cell_center(pf.target), w * 0.2, arcade.color.WHITE)

        brush = self.brush.name.lower()
        if search is None or pf.algorithm is None:
            self.status = f"brush: {brush}  |  no search (source or target blocked)"
        elif not search.done:
            self.status = f"{pf.algorithm.value}: {len(search.tree)} edges in the tree..."
        else:
            result = (
                f"path cost {search.cost_to_target:.1f}, {len(search.path_to_target())} nodes"
                if search.found
                else "no path"
            )
            self.status = (
                f"brush: {brush}  |  {pf.algorithm.value}: {result}, "
                f"{len(search.tree)} tree edges, {pf.time_taken * 1000:.2f} ms"
            )
