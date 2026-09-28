import itertools
import math

import pytest

from gameai.common.graph import (
    GraphEdge,
    NavGraphNode,
    SparseGraph,
    create_grid,
    weight_node_edges,
)
from gameai.common.graph_search import (
    AStarSearch,
    BreadthFirstSearch,
    DepthFirstSearch,
    DijkstraSearch,
    manhattan,
    zero,
)
from gameai.common.vector2d import Vector2D

type Graph = SparseGraph[NavGraphNode, GraphEdge]


def graph_from(
    positions: list[tuple[float, float]], edges: list[tuple[int, int, float]], digraph: bool = False
) -> Graph:
    graph: Graph = SparseGraph(digraph)
    for i, (x, y) in enumerate(positions):
        graph.add_node(NavGraphNode(i, Vector2D(x, y)))
    for a, b, cost in edges:
        graph.add_edge(GraphEdge(a, b, cost))
    return graph


@pytest.fixture
def diamond() -> Graph:
    """0 → 1 → 3 costs 1 + 5, 0 → 2 → 3 costs 3 + 1: fewer edges isn't cheaper here."""
    return graph_from(
        [(0, 0), (1, 1), (1, -1), (2, 0), (3, 0)],
        [(0, 1, 1), (1, 3, 5), (0, 2, 3), (2, 3, 1), (3, 4, 1)],
    )


# --- SparseGraph -----------------------------------------------------------------------------
def test_undirected_edges_are_added_both_ways(diamond: Graph) -> None:
    assert diamond.is_edge_present(1, 0)
    assert diamond.edge(1, 0).cost == 1
    assert diamond.num_edges == 10
    diamond.add_edge(GraphEdge(0, 1, 99))  # duplicate: ignored
    assert diamond.edge(0, 1).cost == 1


def test_digraph_edges_are_one_way() -> None:
    graph = graph_from([(0, 0), (1, 0)], [(0, 1, 1)], digraph=True)
    assert graph.is_edge_present(0, 1)
    assert not graph.is_edge_present(1, 0)


def test_removing_a_node_removes_its_edges_and_keeps_indices(diamond: Graph) -> None:
    diamond.remove_node(3)
    assert not diamond.is_node_present(3)
    assert diamond.num_nodes == 5
    assert diamond.num_active_nodes == 4
    assert not any(e.to_index == 3 for e in diamond.all_edges())
    with pytest.raises(KeyError):
        diamond.node(3)
    diamond.add_node(NavGraphNode(3, Vector2D(2, 0)))  # the slot can be reused
    assert diamond.is_node_present(3)


def test_add_node_rejects_duplicates_and_gaps(diamond: Graph) -> None:
    with pytest.raises(ValueError, match="already exists"):
        diamond.add_node(NavGraphNode(0, Vector2D()))
    with pytest.raises(ValueError, match="skips"):
        diamond.add_node(NavGraphNode(9, Vector2D()))


def test_grid_has_eight_neighbours_with_distance_costs() -> None:
    grid = create_grid(30, 30, 3, 3)
    center = 4
    assert len(list(grid.edges_from(center))) == 8
    assert len(list(grid.edges_from(0))) == 3  # corner
    assert grid.edge(center, 5).cost == pytest.approx(10)
    assert grid.edge(center, 8).cost == pytest.approx(10 * math.sqrt(2))
    assert grid.node(0).position == Vector2D(5, 25)  # row 0 is the top row


def test_weight_node_edges_scales_both_directions() -> None:
    grid = create_grid(30, 30, 3, 3)
    weight_node_edges(grid, 4, 2.0)
    assert grid.edge(4, 5).cost == pytest.approx(20)
    assert grid.edge(5, 4).cost == pytest.approx(20)


# --- searches -------------------------------------------------------------------------------
def test_dfs_finds_a_path(diamond: Graph) -> None:
    search = DepthFirstSearch(diamond, 0, 4).run()
    path = search.path_to_target()
    assert search.found
    assert path[0] == 0
    assert path[-1] == 4
    assert all(diamond.is_edge_present(a, b) for a, b in itertools.pairwise(path))


def test_bfs_finds_the_fewest_edges(diamond: Graph) -> None:
    search = BreadthFirstSearch(diamond, 0, 4).run()
    assert len(search.path_to_target()) == 4  # 3 edges


@pytest.mark.parametrize("search_type", [DijkstraSearch, AStarSearch])
def test_cost_based_searches_find_the_cheapest_path(diamond: Graph, search_type: type) -> None:
    search = search_type(diamond, 0, 4).run()
    assert search.path_to_target() == [0, 2, 3, 4]
    assert search.cost_to_target == 5


def test_unreachable_target() -> None:
    graph = graph_from([(0, 0), (1, 0), (5, 5)], [(0, 1, 1)])
    for search_type in (DepthFirstSearch, BreadthFirstSearch, DijkstraSearch, AStarSearch):
        search = search_type(graph, 0, 2).run()
        assert not search.found
        assert search.path_to_target() == []


def test_dijkstra_without_target_builds_the_whole_tree(diamond: Graph) -> None:
    search = DijkstraSearch(diamond, 0).run()
    assert len(search.tree) == 4  # every other node reached once
    assert search.g_cost == {0: 0, 1: 1, 2: 3, 3: 4, 4: 5}


def test_astar_expands_fewer_nodes_than_dijkstra_on_an_open_grid() -> None:
    grid = create_grid(200, 200, 20, 20)
    source, target = 19 * 20 + 1, 1 * 20 + 18
    dijkstra = DijkstraSearch(grid, source, target).run()
    astar = AStarSearch(grid, source, target).run()
    assert astar.cost_to_target == pytest.approx(dijkstra.cost_to_target)
    assert len(astar.tree) < len(dijkstra.tree) / 2


def test_manhattan_and_zero_heuristics() -> None:
    grid = create_grid(30, 30, 3, 3)
    assert manhattan(grid, 0, 8) == pytest.approx(40)
    assert zero(grid, 0, 8) == 0
    search = AStarSearch(grid, 0, 8, heuristic=manhattan).run()
    assert search.found


def test_steps_yield_one_tree_edge_at_a_time(diamond: Graph) -> None:
    search = DijkstraSearch(diamond, 0, 4)
    steps = search.steps()
    first = next(steps)
    assert (first.from_index, first.to_index) == (0, 1)  # the cheapest edge out of the source
    assert not search.done
    rest = list(steps)
    assert search.done
    assert [first, *rest] == search.tree


def test_search_records_each_node_parent() -> None:
    graph = graph_from([(0, 0), (1, 0), (2, 0)], [(0, 1, 1), (1, 2, 1)])
    search = BreadthFirstSearch(graph, 0, 2).run()
    assert search.parent == {0: 0, 1: 0, 2: 1}
