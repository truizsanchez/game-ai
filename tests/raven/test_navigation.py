from collections.abc import Callable
from enum import Enum

import pytest

from gameai.common.geometry import Wall2D
from gameai.common.graph import EdgeBehavior
from gameai.common.messaging import Telegram
from gameai.common.vector2d import Vector2D
from gameai.raven.entity_types import EntityType, Message
from gameai.raven.game import RavenGame
from gameai.raven.navigation import (
    PathEdge,
    PathManager,
    PathPlanner,
    SearchStatus,
    smooth_precise,
    smooth_quick,
)
from gameai.raven.path_brain import PathBrain
from tests.raven.conftest import place

type GameFactory = Callable[..., RavenGame]


def straight_line(n: int) -> list[PathEdge]:
    """n unit edges along the x axis."""
    return [PathEdge(Vector2D(i, 0), Vector2D(i + 1, 0)) for i in range(n)]


def always(a: Vector2D, b: Vector2D) -> bool:
    return True


def never(a: Vector2D, b: Vector2D) -> bool:
    return False


# --- smoothing ---------------------------------------------------------------------------------
def test_smoothing_merges_a_clear_path_into_one_edge() -> None:
    for smooth in (smooth_quick, smooth_precise):
        [edge] = smooth(straight_line(5), always)
        assert (edge.source, edge.destination) == (Vector2D(0, 0), Vector2D(5, 0))


def test_smoothing_keeps_a_blocked_path() -> None:
    for smooth in (smooth_quick, smooth_precise):
        assert smooth(straight_line(4), never) == straight_line(4)


def test_smoothing_never_merges_door_edges() -> None:
    path = straight_line(3)
    path[1] = PathEdge(path[1].source, path[1].destination, EdgeBehavior.GOES_THROUGH_DOOR, 7)
    for smooth in (smooth_quick, smooth_precise):
        assert [e.behavior for e in smooth(path, always)] == [
            EdgeBehavior.NORMAL,
            EdgeBehavior.GOES_THROUGH_DOOR,
            EdgeBehavior.NORMAL,
        ]


def test_precise_smoothing_sees_past_a_blocked_shortcut() -> None:
    """From edge 0 the bot can reach the end of edge 2 but not the end of edge 1."""

    def blocked_to_2(a: Vector2D, b: Vector2D) -> bool:
        return b != Vector2D(2, 0)

    path = straight_line(3)
    assert len(smooth_quick(path, blocked_to_2)) == 2  # 0-1 can't merge, 1-2 can
    [edge] = smooth_precise(path, blocked_to_2)
    assert edge.destination == Vector2D(3, 0)


# --- the planner ---------------------------------------------------------------------------------
def planner_for(game: RavenGame, x: float, y: float) -> PathPlanner:
    bot = place(game.bots[0], x, y)
    return bot.path_planner


def run_search(game: RavenGame, planner: PathPlanner) -> SearchStatus:
    status = SearchStatus.INCOMPLETE
    while status is SearchStatus.INCOMPLETE:
        status = planner.cycle_once()
    return status


def test_closest_node_is_the_nearest_reachable_one(make_game: GameFactory) -> None:
    game = make_game(bots=1)
    planner = planner_for(game, 55, 145)
    assert planner.closest_node_to(Vector2D(55, 145)) == 0


def test_directly_walkable_target_needs_no_search(make_game: GameFactory) -> None:
    game = make_game(bots=1)
    planner = planner_for(game, 50, 100)
    assert planner.request_path_to_position(Vector2D(150, 100))
    assert planner.is_direct
    [edge] = planner.path()
    assert edge.destination == Vector2D(150, 100)


def test_path_through_the_graph_around_a_wall(make_game: GameFactory) -> None:
    game = make_game(bots=1)
    # A wall down the middle, open at the bottom; the graph loses the nodes it covers.
    game.map.walls.append(Wall2D(Vector2D(100, 190), Vector2D(100, 75)))
    game.map.walls.append(Wall2D(Vector2D(101, 75), Vector2D(101, 190)))
    for node in (1, 4):
        game.map.graph.remove_node(node)
    planner = planner_for(game, 50, 150)
    assert planner.request_path_to_position(Vector2D(150, 150))
    assert not planner.is_direct
    assert run_search(game, planner) is SearchStatus.FOUND
    path = planner.path()
    assert path[0].source == Vector2D(50, 150)
    assert path[-1].destination == Vector2D(150, 150)
    assert min(e.destination.y for e in path) <= 50  # went around the bottom of the wall


def test_item_search_finds_the_closest_active_item(make_game: GameFactory) -> None:
    game = make_game(bots=1)
    planner = planner_for(game, 60, 60)
    assert planner.request_path_to_item(EntityType.HEALTH)
    assert run_search(game, planner) is SearchStatus.FOUND
    assert planner.path()[-1].destination == Vector2D(150, 150)  # node 2, the health pack
    health = game.map.graph.node(2).extra
    health.deactivate()
    assert planner.request_path_to_item(EntityType.HEALTH)
    assert run_search(game, planner) is SearchStatus.NOT_FOUND


def test_cost_estimates_use_the_path_cost_table(make_game: GameFactory) -> None:
    game = make_game(bots=1)
    planner = planner_for(game, 50, 150)  # on node 0
    assert planner.cost_to_node(8) == pytest.approx(2 * 50 * 2**0.5)
    assert planner.cost_to_closest_item(EntityType.HEALTH) == pytest.approx(100)
    assert planner.cost_to_closest_item(EntityType.RAIL_GUN) is None


def test_planner_tells_the_bot_when_the_path_is_ready(make_game: GameFactory) -> None:
    game = make_game(bots=1)
    bot = place(game.bots[0], 60, 60)
    received: list[Enum] = []
    original = bot.handle_message

    def recording(telegram: Telegram) -> bool:
        received.append(telegram.msg)
        return original(telegram)

    bot.handle_message = recording  # type: ignore[method-assign]
    bot.position = Vector2D(150, 150)  # away from the shotgun, so the search takes cycles
    bot.path_planner.request_path_to_item(EntityType.SHOTGUN)
    for _ in range(3):
        game.path_manager.update_searches()
    assert received == [Message.PATH_READY]


def test_path_manager_shares_its_budget_round_robin(make_game: GameFactory) -> None:
    game = make_game(bots=2)
    manager = PathManager(cycles_per_update=2)
    game.path_manager = manager
    a, b = (place(bot, 60, 60).path_planner for bot in game.bots)
    a.request_path_to_item(EntityType.HEALTH)
    b.request_path_to_item(EntityType.SHOTGUN)
    assert manager.requests == [a, b]
    manager.update_searches()  # one cycle each
    assert a.search is not None
    assert len(a.search.tree) == 1  # a settled one node besides its source
    assert manager.requests == [a]  # b starts on the shotgun: found in its first cycle
    for _ in range(20):
        manager.update_searches()
    assert manager.requests == []


# --- the chapter 8 brain -------------------------------------------------------------------------
def test_bots_explore_by_following_paths(make_game: GameFactory) -> None:
    game = make_game(bots=1)
    bot = place(game.bots[0], 50, 150)
    assert isinstance(bot.brain, PathBrain)
    visited = set()
    for _ in range(60 * 30):
        game.update()
        visited.add(game.map.graph.node(bot.path_planner.closest_node_to(bot.position) or 0).index)
    assert len(visited) >= 5  # it gets around the room


def test_possessed_bot_goes_to_the_clicked_position(make_game: GameFactory) -> None:
    game = make_game(bots=1)
    bot = place(game.bots[0], 50, 150)
    game.click_right(bot.position)
    game.click_right(bot.position)
    game.click_right(Vector2D(150, 50))
    for _ in range(400):
        game.update()
    assert bot.is_at_position(Vector2D(150, 50))
    assert not bot.brain.path  # type: ignore[attr-defined]


def test_stuck_bot_replans(make_game: GameFactory) -> None:
    game = make_game(bots=1)
    bot = place(game.bots[0], 50, 150)
    brain = bot.brain
    assert isinstance(brain, PathBrain)
    brain.path = [PathEdge(bot.position, Vector2D(150, 150))]
    brain.destinations = [Vector2D(150, 150)]
    requests: list[Vector2D] = []
    request = bot.path_planner.request_path_to_position

    def recording(target: Vector2D) -> bool:
        requests.append(target)
        return request(target)

    bot.path_planner.request_path_to_position = recording  # type: ignore[method-assign]
    for _ in range(60 * 6):  # the bot never moves (no game update): the edge times out
        brain.process()
        game.tick += 1
    assert requests == [Vector2D(150, 150)]  # replanned to the same destination
