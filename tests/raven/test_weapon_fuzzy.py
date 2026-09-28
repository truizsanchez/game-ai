from collections.abc import Callable

import pytest

from gameai.raven.entity_types import EntityType
from gameai.raven.game import RavenGame
from gameai.raven.weapon_fuzzy import MODULE_BUILDERS, desirability
from tests.raven.conftest import place

type GameFactory = Callable[..., RavenGame]


def score(weapon: EntityType, distance: float, ammo: int | None = 20) -> float:
    return desirability(MODULE_BUILDERS[weapon](), distance, ammo)


def test_each_weapon_has_its_range() -> None:
    close = {w: score(w, 30, None if w is EntityType.BLASTER else 20) for w in MODULE_BUILDERS}
    far = {w: score(w, 400, None if w is EntityType.BLASTER else 20) for w in MODULE_BUILDERS}
    assert max(close, key=close.__getitem__) is EntityType.SHOTGUN
    assert max(far, key=far.__getitem__) is EntityType.RAIL_GUN


def test_rockets_are_for_medium_range() -> None:
    assert score(EntityType.ROCKET_LAUNCHER, 150) > score(EntityType.ROCKET_LAUNCHER, 30)
    assert score(EntityType.ROCKET_LAUNCHER, 150) > score(EntityType.ROCKET_LAUNCHER, 400)


def test_more_ammo_is_more_desirable() -> None:
    assert score(EntityType.RAIL_GUN, 200, 40) > score(EntityType.RAIL_GUN, 200, 2)


def test_weapons_use_their_fuzzy_module(make_game: GameFactory) -> None:
    game = make_game()
    me, enemy = game.bots
    place(me, 20, 100)
    place(enemy, 50, 100)  # close: the shotgun should win
    me.targeting.target = enemy
    for weapon in (EntityType.SHOTGUN, EntityType.RAIL_GUN, EntityType.ROCKET_LAUNCHER):
        me.weapons.add_weapon(weapon)
    me.weapons.select_weapon()
    assert me.weapons.current.type is EntityType.SHOTGUN
    shotgun = me.weapons.weapon(EntityType.SHOTGUN)
    assert shotgun is not None
    assert shotgun.last_desirability == pytest.approx(score(EntityType.SHOTGUN, 30, 15))


def test_empty_weapons_score_zero(make_game: GameFactory) -> None:
    game = make_game(bots=1)
    bot = place(game.bots[0], 20, 100)
    bot.weapons.add_weapon(EntityType.ROCKET_LAUNCHER)
    rockets = bot.weapons.weapon(EntityType.ROCKET_LAUNCHER)
    assert rockets is not None
    rockets.rounds_left = 0
    assert rockets.desirability(150) == 0.0
