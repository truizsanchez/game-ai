# Chapter 8 — Practical Path Planning

Run: `uv run python -m gameai.raven`. Bots now explore the map by planning paths through the
navigation graph, and a possessed bot follows a planned path to each right-clicked point.
Keys:
- `G`: the graph.
- `S`: cycle path smoothing (off / quick / precise).
- `L`: labels.

The selected bot's current path is drawn in blue.

## Book sections → code

| Book section | Code |
|---|---|
| The Raven navigation graph (points of visibility, expanded geometry, NavMesh) | Theory; Raven loads hand-built graphs from the `.map` files (`raven.map`) |
| Creating a path planner class: planning to a position | `raven.navigation.PathPlanner.request_path_to_position` (A\*) |
| Planning a path to an item type | `PathPlanner.request_path_to_item` (Dijkstra with an "active item of this type" termination condition) |
| Paths as nodes or paths as edges? Annotated edges | `raven.navigation.PathEdge` keeps each edge's `EdgeBehavior` flags and door ID |
| Path smoothing: rough but quick, precise but slow | `smooth_quick`, `smooth_precise` |
| Methods for reducing CPU overhead: precalculated costs | `RavenMap.path_costs`, `PathPlanner.cost_to_node`, `cost_to_closest_item` |
| Time-sliced path planning; the path manager | `raven.navigation.PathManager` + the search generators in `gameai.common.graph_search` |
| Getting out of sticky situations | `raven.path_brain.PathBrain`: a deadline per edge, and replanning when it passes |

## Design decisions and deviations

- **No separate time-sliced search classes.** The C++ code duplicates A\* and Dijkstra as
  `Graph_SearchAStar_TS` and `Graph_SearchDijkstras_TS` with a `CycleOnce` method. In the
  port every search in `gameai.common.graph_search` is already a generator: advancing it
  once is `CycleOnce`. `PathPlanner.cycle_once` does exactly that, then messages the bot
  `PATH_READY` or `NO_PATH_AVAILABLE` when the search ends.
- **Termination conditions are a callable** (`is_target=...`) passed to the search, instead
  of a template policy class (`FindNodeIndex`, `FindActiveTrigger`).
- **The path manager** shares `max_search_cycles_per_update_step` cycles per update among
  the pending searches, one cycle each in turn, as in the C++ code.
- **A directly walkable target needs no search.** `request_path_to_position` records this
  (`is_direct`), and `path()` returns the single straight edge. The C++ planner returns true
  without registering a search, and leaves the caller to notice that no message will arrive.
- **Smoothing never merges edges that aren't plain walking.** The C++ smoothing only checks
  the flags of the edge being absorbed, so a door edge could be stretched past its door.
- **The chapter 8 brain** (`PathBrain`) implements "explore by planning paths to random
  nodes" and "go where the player clicks". While a search runs, the bot seeks straight at the
  destination, and each edge has a time limit. It is the same behavior chapter 9 builds from
  goals (`Goal_Explore`, `Goal_MoveToPosition`, `Goal_FollowPath`, `Goal_TraverseEdge`),
  written as plain code first. Doors are negotiated in chapter 9: here a bot facing a closed
  door times out and replans.

## Tests

`tests/raven/test_navigation.py` covers:
- **Smoothing:** a clear path collapses to one edge, a blocked path is left alone, door edges
  are never merged, and precise smoothing looks further ahead than quick smoothing.
- **Planning:** closest reachable node, direct paths, planning around a wall, the closest
  active item (and none when it's inactive), cost estimates from the cost table, and the
  `PATH_READY` message.
- **The path manager** sharing its budget round-robin.
- **The chapter 8 brain:** exploring, reaching a clicked point, and replanning after a timeout.
