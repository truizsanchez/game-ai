# Chapter 5 — The Secret Life of Graphs

Run: `uv run python -m gameai.ch05_graphs`, the Pathfinder tool.

- **Painting terrain** (click or drag): `X` obstacle, `W` water, `M` mud, `E` normal, `S`
  source, `T` target.
- **Choosing a search:** `F` depth first, `B` breadth first, `D` Dijkstra, `A` A\*.
- **Animating:** `Space` replays the current search one tree edge per tick.
- **Other keys:** `G` shows the graph, `C` clears the grid, and `L` cycles through the
  original `.map` files, loaded from the private sources directory.

On the original `test_with_walls.map`:

| Search | Path | Cost | Tree edges |
|---|---|---|---|
| DFS | 177 nodes, winding everywhere | 5296.5 | 179 |
| BFS | 22 nodes (fewest edges) | 661.6 | 186 |
| Dijkstra | 22 nodes, cheapest | 639.8 | 191 |
| A\* (Euclidean) | the same cheapest path | 639.8 | 91 |

Dijkstra and A\* return the same path, but A\* explores less than half as many nodes.
`test_original_map_gives_the_expected_ranking` checks this ranking, and is skipped when
the maps aren't available (e.g. in CI).

## Book sections → code

| Book section | Code |
|---|---|
| Graphs, digraphs, navigation graphs | `gameai.common.graph` |
| The GraphNode, GraphEdge and SparseGraph classes | `GraphNode`, `NavGraphNode`, `GraphEdge`, `SparseGraph` |
| Depth First Search | `gameai.common.graph_search.DepthFirstSearch` |
| Breadth First Search | `BreadthFirstSearch` |
| Edge relaxation, shortest path trees, Dijkstra's algorithm | `DijkstraSearch` |
| A\*, Manhattan heuristic | `AStarSearch`, `euclidean`, `manhattan`, `noisy_euclidean`, `zero` |
| Grid helpers (`HandyGraphFunctions.h`) | `create_grid`, `add_all_neighbours_to_grid_node`, `weight_node_edges` |
| The Pathfinder demo | `ch05_graphs.pathfinder.Pathfinder`, `ch05_graphs.demo` |

## Design decisions and deviations

- **Searches are generators.** `search.steps()` yields each edge as it joins the search tree;
  `search.run()` exhausts it. The demo uses the steps to animate, and chapter 8's time-sliced
  path planning will use them to spread a search over several frames. The C++ code needs
  separate time-sliced classes for that.
- **Dijkstra is A\* with a zero heuristic** (`DijkstraSearch(AStarSearch)`), which is exactly
  how the book relates them. Without a target it builds the full shortest path tree.
- **`heapq` with lazy deletion** instead of the C++ indexed priority queue. When a node's cost
  improves, a new entry is pushed and stale entries are skipped when popped. This is the
  standard way in Python, and it keeps the algorithm as the book describes it.
- **Adjacency dicts.** Each node's outgoing edges are a `dict` keyed by destination, so
  duplicate edges are impossible and `edge(a, b)` is O(1). The C++ code searches a list.
- **Removed nodes leave `None`** in the node list, instead of an `invalid_node_index` marker,
  so the other indices stay valid. Iterating a graph yields only active nodes.
- **DFS skips nodes that are already visited** when they are popped. The C++ version checks
  only when pushing, so a node can enter the tree twice when two stacked edges lead to it.
- **Map files** keep the original format: cell counts, then one terrain value per cell, with
  row 0 at the top. They are read from the original distribution
  (`gameai.common.sources.original_file`, overridable with `GAMEAI_ORIGINAL_SOURCE`) and not
  copied into the repository.
- **C++ bug not ported:** `UpdateGraphFromBrush` computes a cell's row with `CellIndex /
  m_iCellsY` (it should divide by the number of columns). This only works because the default
  grid is square.
