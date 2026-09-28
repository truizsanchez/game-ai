from pathlib import Path

import pytest

from gameai.ch05_graphs.pathfinder import Algorithm, Pathfinder, Terrain
from gameai.common.sources import original_file
from gameai.common.vector2d import Vector2D


@pytest.fixture
def pathfinder() -> Pathfinder:
    return Pathfinder(5, 5, 50, 50)


def test_cell_lookup_uses_row_zero_at_the_top(pathfinder: Pathfinder) -> None:
    assert pathfinder.cell_at(Vector2D(5, 45)) == 0
    assert pathfinder.cell_at(Vector2D(45, 5)) == 24
    assert pathfinder.cell_at(Vector2D(60, 5)) is None
    assert pathfinder.cell_center(0) == Vector2D(5, 45)


def test_obstacles_block_and_are_avoided(pathfinder: Pathfinder) -> None:
    pathfinder.source, pathfinder.target = 10, 14  # middle row, left to right
    for cell in (2, 7, 12, 17):  # a wall down the middle column, open at the bottom
        pathfinder.paint(cell, Terrain.OBSTACLE)
    search = pathfinder.run(Algorithm.ASTAR)
    assert search.found
    assert not {2, 7, 12, 17} & set(search.path_to_target())
    assert 22 in search.path_to_target()  # the only way around


def test_restoring_an_obstacle_reconnects_the_cell(pathfinder: Pathfinder) -> None:
    pathfinder.paint(12, Terrain.OBSTACLE)
    pathfinder.paint(12, Terrain.NORMAL)
    assert len(list(pathfinder.graph.edges_from(12))) == 8


def test_water_is_avoided_when_cheaper_to_go_around(pathfinder: Pathfinder) -> None:
    pathfinder.source, pathfinder.target = 10, 14
    pathfinder.paint(12, Terrain.WATER)
    path = pathfinder.run(Algorithm.DIJKSTRA).path_to_target()
    assert 12 not in path
    straight = pathfinder.run(Algorithm.BFS).path_to_target()
    assert len(straight) == 5  # BFS ignores costs: any 4-edge path will do


def test_blocked_source_means_no_search(pathfinder: Pathfinder) -> None:
    pathfinder.paint(pathfinder.source, Terrain.OBSTACLE)
    pathfinder.run(Algorithm.ASTAR)
    assert pathfinder.search is None


def test_save_and_load_round_trip(pathfinder: Pathfinder, tmp_path: Path) -> None:
    pathfinder.paint(3, Terrain.MUD)
    pathfinder.paint(7, Terrain.OBSTACLE)
    pathfinder.paint(0, Terrain.SOURCE)
    pathfinder.paint(24, Terrain.TARGET)
    file = tmp_path / "test.map"
    pathfinder.save(file)
    loaded = Pathfinder.load(file, 50, 50)
    assert loaded.terrain == pathfinder.terrain
    assert (loaded.source, loaded.target) == (0, 24)
    assert file.read_text().split()[:2] == ["5", "5"]


@pytest.mark.skipif(
    original_file("Buckland_Chapter5-Pathfinder", "test_with_walls.map") is None,
    reason="original map files are not available",
)
def test_original_map_gives_the_expected_ranking() -> None:
    path = original_file("Buckland_Chapter5-Pathfinder", "test_with_walls.map")
    assert path is not None
    pf = Pathfinder.load(path, 500, 500)
    results = {a: pf.run(a) for a in Algorithm}
    dfs, bfs = results[Algorithm.DFS], results[Algorithm.BFS]
    dijkstra, astar = results[Algorithm.DIJKSTRA], results[Algorithm.ASTAR]
    assert all(r.found for r in results.values())
    assert len(bfs.path_to_target()) <= len(dfs.path_to_target())
    assert astar.cost_to_target == pytest.approx(dijkstra.cost_to_target)
    assert dijkstra.cost_to_target <= bfs.cost_to_target
    assert len(astar.tree) < len(dijkstra.tree)
