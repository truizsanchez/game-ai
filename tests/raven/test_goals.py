from collections.abc import Callable
from pathlib import Path

import pytest

from gameai.common.vector2d import Vector2D
from gameai.raven.entity_types import EntityType
from gameai.raven.game import RavenGame
from gameai.raven.goal_think import (
    AttackTargetEvaluator,
    ExploreEvaluator,
    GetHealthEvaluator,
    GetWeaponEvaluator,
    GoalThink,
    distance_to_item,
    total_weapon_strength,
)
from gameai.raven.goals import AttackTarget, GetItem, HuntTarget, MoveToPosition
from tests.raven.conftest import place

type GameFactory = Callable[..., RavenGame]


def brain_of(game: RavenGame, index: int = 0) -> GoalThink:
    brain = game.bots[index].brain
    assert isinstance(brain, GoalThink)
    return brain


# --- features and evaluators ---------------------------------------------------------------------
def test_features(make_game: GameFactory) -> None:
    game = make_game(bots=1)
    bot = place(game.bots[0], 50, 150)  # node 0: 100 from the health pack
    assert distance_to_item(bot, EntityType.HEALTH) == pytest.approx(100 / 500)
    assert distance_to_item(bot, EntityType.RAIL_GUN) == 1.0  # none on the map
    assert total_weapon_strength(bot) == pytest.approx(0.1)
    bot.weapons.add_weapon(EntityType.SHOTGUN)
    assert total_weapon_strength(bot) == pytest.approx(0.1 + 0.9 * 15 / 150)


def test_health_evaluator_wants_health_when_hurt(make_game: GameFactory) -> None:
    game = make_game(bots=1)
    bot = place(game.bots[0], 50, 150)
    evaluator = GetHealthEvaluator(bias=1.0)
    assert evaluator.evaluate(bot) == 0.0  # full health
    bot.health = 20
    assert evaluator.evaluate(bot) == pytest.approx(0.2 * 0.8 / 0.2)


def test_weapon_evaluator_needs_an_available_weapon(make_game: GameFactory) -> None:
    game = make_game(bots=1)
    bot = place(game.bots[0], 50, 150)
    assert GetWeaponEvaluator(1.0, EntityType.RAIL_GUN).evaluate(bot) == 0.0
    assert GetWeaponEvaluator(1.0, EntityType.SHOTGUN).evaluate(bot) > 0.0


def test_attack_needs_a_target_and_explore_is_constant(make_game: GameFactory) -> None:
    game = make_game()
    me, enemy = game.bots
    place(me, 50, 100)
    place(enemy, 150, 100)
    assert AttackTargetEvaluator(1.0).evaluate(me) == 0.0
    me.targeting.target = enemy
    assert AttackTargetEvaluator(1.0).evaluate(me) == pytest.approx(0.1)
    assert ExploreEvaluator(2.0).evaluate(me) == pytest.approx(0.1)


def test_arbitration_picks_the_most_desirable_goal(make_game: GameFactory) -> None:
    game = make_game()
    me, enemy = game.bots
    place(me, 50, 150)
    place(enemy, 150, 50)
    brain = brain_of(game)
    for evaluator in brain.evaluators:
        evaluator.bias = 1.0
    me.health = 10
    brain.arbitrate()
    assert isinstance(brain.subgoals[0], GetItem)
    assert brain.subgoals[0].item_type is EntityType.HEALTH
    me.health = me.max_health
    for _ in range(4):  # full of shotgun ammo: fetching more isn't worth it
        me.weapons.add_weapon(EntityType.SHOTGUN)
    me.targeting.target = enemy
    brain.arbitrate()
    assert isinstance(brain.subgoals[0], AttackTarget)


def test_same_goal_is_not_restarted(make_game: GameFactory) -> None:
    game = make_game(bots=1)
    place(game.bots[0], 50, 150)
    brain = brain_of(game)
    brain.add_goal_explore()
    first = brain.subgoals[0]
    brain.add_goal_explore()
    assert brain.subgoals == [first]


# --- goals in play -------------------------------------------------------------------------------
def test_bot_fetches_the_shotgun(make_game: GameFactory) -> None:
    game = make_game(bots=1)
    bot = place(game.bots[0], 150, 150)
    brain = brain_of(game)
    brain.add_goal_get_item(EntityType.SHOTGUN)
    for _ in range(60 * 10):
        game.update()
        if bot.weapons.weapon(EntityType.SHOTGUN):
            break
    assert bot.weapons.weapon(EntityType.SHOTGUN) is not None


def test_queued_moves_visit_each_position(make_game: GameFactory) -> None:
    game = make_game(bots=1)
    bot = place(game.bots[0], 50, 150)
    game.click_right(bot.position)
    game.click_right(bot.position)
    game.click_right(Vector2D(150, 150))
    game.click_right(Vector2D(150, 50), queue=True)
    brain = brain_of(game)
    assert [type(g) for g in brain.subgoals] == [MoveToPosition, MoveToPosition]
    visited = []
    for _ in range(60 * 10):
        game.update()
        for target in (Vector2D(150, 150), Vector2D(150, 50)):
            if bot.is_at_position(target) and target not in visited:
                visited.append(target)
    assert visited == [Vector2D(150, 150), Vector2D(150, 50)]


def test_bot_goes_through_a_door_using_its_switch(make_game: GameFactory, door_path: Path) -> None:
    game = make_game(door_path, bots=1)
    bot = place(game.bots[0], 30, 50)
    [door] = game.map.doors
    game.click_right(bot.position)
    game.click_right(bot.position)
    game.click_right(Vector2D(170, 50))
    opened = False
    for _ in range(60 * 30):
        game.update()
        opened |= door.status.name != "CLOSED"
        if bot.is_at_position(Vector2D(170, 50)):
            break
    assert opened
    assert bot.is_at_position(Vector2D(170, 50))


def test_hunting_goes_to_where_the_target_was_last_seen(make_game: GameFactory) -> None:
    game = make_game()
    me, enemy = game.bots
    place(me, 50, 150)
    place(enemy, 150, 50)
    me.memory.update_vision()
    me.targeting.update()
    enemy.position = Vector2D(150, 150)  # moved since it was last seen
    me.facing = Vector2D(-1, 0)  # and now out of view
    me.memory.update_vision()
    hunt = HuntTarget(me)
    hunt.activate()
    [move] = hunt.subgoals
    assert isinstance(move, MoveToPosition)
    assert move.destination == Vector2D(150, 50)


def test_a_goal_driven_match_runs(make_game: GameFactory) -> None:
    game = make_game(bots=3)
    names = set()
    for i in range(60 * 30):
        game.update()
        if i % 30 == 0:
            for bot in game.bots:
                brain = bot.brain
                if bot.is_alive and isinstance(brain, GoalThink) and brain.subgoals:
                    names.add(brain.subgoals[0].name)
    assert len(names) >= 2
