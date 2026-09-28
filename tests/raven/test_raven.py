from collections.abc import Callable
from pathlib import Path

import pytest

from gameai.common.vector2d import Vector2D
from gameai.raven.entity_types import EntityType, Message
from gameai.raven.game import RavenGame, original_map
from gameai.raven.items import DoorStatus, HealthGiver, WeaponGiver
from gameai.raven.projectiles import Bolt, Pellet, Rocket, Slug
from tests.raven.conftest import place

type GameFactory = Callable[..., RavenGame]


# --- map loading ------------------------------------------------------------------------------
def test_room_map_loads_and_flips_y(make_game: GameFactory) -> None:
    game = make_game()
    m = game.map
    assert (m.size_x, m.size_y) == (200, 200)
    assert m.graph.num_active_nodes == 9
    assert m.graph.node(0).position == Vector2D(50, 150)  # y-down 50 → y-up 150
    assert m.spawn_points == [Vector2D(30, 170), Vector2D(170, 30)]
    assert len(m.walls) == 4
    center = Vector2D(100, 100)
    assert all(w.normal.dot(center - w.center) > 0 for w in m.walls)  # all face the room


def test_items_are_attached_to_graph_nodes(make_game: GameFactory) -> None:
    game = make_game()
    health = game.map.graph.node(2).extra
    shotgun = game.map.graph.node(6).extra
    assert isinstance(health, HealthGiver)
    assert health.health_given == 50
    assert isinstance(shotgun, WeaponGiver)
    assert shotgun.entity_type is EntityType.SHOTGUN
    assert game.entities.get(22) is health  # type: ignore[comparison-overlap]  # map ids kept


def test_bots_get_ids_after_the_map_entities(make_game: GameFactory) -> None:
    game = make_game()
    assert [b.id for b in game.bots] == [24, 25]


def test_path_costs_table(make_game: GameFactory) -> None:
    costs = make_game().map.path_costs
    assert costs[0][8] == pytest.approx(2 * 50 * 2**0.5)
    assert costs[0][1] == pytest.approx(50)


# --- doors -------------------------------------------------------------------------------------
def test_switch_opens_the_door_which_closes_again(make_game: GameFactory, door_path: Path) -> None:
    game = make_game(door_path, bots=1)
    [door] = game.map.doors
    assert door.status is DoorStatus.CLOSED
    assert not game.is_los_okay(Vector2D(50, 50), Vector2D(150, 50))
    game.dispatcher.dispatch(Message.OPEN_SESAME, -1, door.id)
    for _ in range(100):
        game.map.update_doors()
    assert door.status is DoorStatus.OPEN  # type: ignore[comparison-overlap]
    assert game.is_los_okay(Vector2D(50, 50), Vector2D(150, 50))
    for _ in range(200):
        game.map.update_doors()
    assert door.status is DoorStatus.CLOSED
    assert game.closest_switch_position(Vector2D(40, 50), door.id) == Vector2D(60, 50)


def test_touching_the_switch_sends_open_sesame(make_game: GameFactory, door_path: Path) -> None:
    game = make_game(door_path, bots=1)
    place(game.bots[0], 60, 50)
    [door] = game.map.doors
    for _ in range(30):  # enough for the trigger regulator to fire
        game.update()
    assert door.status is not DoorStatus.CLOSED


# --- triggers ------------------------------------------------------------------------------------
def test_health_pack_heals_and_respawns(make_game: GameFactory) -> None:
    game = make_game(bots=1)
    bot = place(game.bots[0], 150, 150)  # on the health pack (node 2)
    bot.health = 10
    health = game.map.graph.node(2).extra
    for _ in range(30):
        game.update()
    assert bot.health == 60
    assert not health.active
    for _ in range(game.params.seconds_to_ticks(game.params.items.health_respawn_delay)):
        health.update()
    assert health.active


def test_weapon_pickup_adds_the_weapon_then_ammo(make_game: GameFactory) -> None:
    game = make_game(bots=1)
    bot = place(game.bots[0], 0, 0)
    weapons = bot.weapons
    weapons.add_weapon(EntityType.SHOTGUN)
    assert weapons.ammo_for(EntityType.SHOTGUN) == 15
    weapons.add_weapon(EntityType.SHOTGUN)
    assert weapons.ammo_for(EntityType.SHOTGUN) == 30
    for _ in range(3):
        weapons.add_weapon(EntityType.SHOTGUN)
    assert weapons.ammo_for(EntityType.SHOTGUN) == 50  # capped


# --- perception and targeting ---------------------------------------------------------------------
def test_vision_needs_line_of_sight_and_fov(make_game: GameFactory) -> None:
    game = make_game()
    me, other = game.bots
    place(me, 50, 100, facing=Vector2D(1, 0))
    place(other, 150, 100)
    me.memory.update_vision()
    assert me.memory.is_within_fov(other)
    assert me.memory.is_shootable(other)
    me.facing = Vector2D(-1, 0)  # looking away: still shootable, not seen
    me.memory.update_vision()
    assert not me.memory.is_within_fov(other)
    assert me.memory.is_shootable(other)


def test_gunshots_are_heard(make_game: GameFactory) -> None:
    game = make_game()
    me, other = game.bots
    place(me, 50, 100, facing=Vector2D(-1, 0))
    place(other, 150, 100)
    game.dispatcher.dispatch(Message.GUNSHOT_SOUND, -1, me.id, extra=other)
    assert other in me.memory.recently_sensed_opponents()


def test_targeting_picks_the_closest_sensed_opponent(make_game: GameFactory) -> None:
    game = make_game(bots=3)
    me, near, far = game.bots
    place(me, 50, 100)
    place(near, 100, 100)
    place(far, 180, 100)
    me.memory.update_vision()
    me.targeting.update()
    assert me.targeting.target is near
    near.reduce_health(1000)
    me.targeting.update()
    assert me.targeting.target is far


# --- weapons and projectiles ----------------------------------------------------------------------
def test_shooting_spawns_projectiles_and_noise(make_game: GameFactory) -> None:
    game = make_game(bots=1)
    bot = place(game.bots[0], 50, 100)
    game.tick = 100  # past the weapon's initial cooldown
    bot.fire_weapon(Vector2D(150, 100))
    assert [type(p) for p in game.projectiles] == [Bolt]
    assert any(t.__class__.__name__ == "SoundNotify" for t in game.map.triggers.triggers)
    bot.fire_weapon(Vector2D(150, 100))  # still cooling down
    assert len(game.projectiles) == 1


def test_bolt_damages_the_bot_it_hits(make_game: GameFactory) -> None:
    game = make_game()
    shooter, victim = game.bots
    place(shooter, 50, 100)
    place(victim, 80, 100)
    game.tick = 100
    shooter.fire_weapon(victim.position)
    for _ in range(10):
        for p in game.projectiles:
            p.update()
    assert victim.health == victim.max_health - game.params.projectiles["bolt"].damage
    assert victim.hit_ticks_left > 0


def test_slug_passes_through_bots_but_not_walls(make_game: GameFactory) -> None:
    game = make_game(bots=3)
    shooter, first, second = game.bots
    place(shooter, 30, 100)
    place(first, 80, 100)
    place(second, 120, 100)
    game.tick = 100
    shooter.weapons.add_weapon(EntityType.RAIL_GUN)
    shooter.change_weapon(EntityType.RAIL_GUN)
    game.tick += 1  # a weapon picked up now can fire from the next instant
    shooter.fire_weapon(Vector2D(400, 100))  # beyond the east wall at x=190
    [slug] = game.projectiles
    slug.update()
    assert isinstance(slug, Slug)
    assert slug.impact_point.x == pytest.approx(190)
    damage = game.params.projectiles["slug"].damage
    assert first.health == second.health == first.max_health - damage


def test_rocket_blast_hurts_everyone_nearby(make_game: GameFactory) -> None:
    game = make_game(bots=3)
    shooter, target, bystander = game.bots
    place(shooter, 30, 100)
    place(target, 120, 100)
    place(bystander, 120, 115)
    game.tick = 100
    shooter.weapons.add_weapon(EntityType.ROCKET_LAUNCHER)
    shooter.change_weapon(EntityType.ROCKET_LAUNCHER)
    game.tick += 1  # a weapon picked up now can fire from the next instant
    shooter.fire_weapon(target.position)
    for _ in range(60):
        for p in list(game.projectiles):
            p.update()
    damage = game.params.projectiles["rocket"].damage
    assert target.health == target.max_health - 2 * damage  # direct hit + blast
    assert bystander.health == bystander.max_health - damage
    assert all(isinstance(p, Rocket) and p.dead for p in game.projectiles)


def test_shotgun_spreads_pellets_around_the_aim(make_game: GameFactory) -> None:
    game = make_game(bots=1)
    shooter = place(game.bots[0], 30, 100)
    game.tick = 100
    shooter.weapons.add_weapon(EntityType.SHOTGUN)
    shooter.change_weapon(EntityType.SHOTGUN)
    game.tick += 1  # a weapon picked up now can fire from the next instant
    shooter.fire_weapon(Vector2D(130, 100))
    assert len(game.projectiles) == 10
    assert all(isinstance(p, Pellet) for p in game.projectiles)
    # Spread is about the shooter: every aim point stays near the target, whatever the map origin.
    assert all(abs(p.target.y - 100) < 10 for p in game.projectiles)


def test_weapon_selection_prefers_the_right_range(make_game: GameFactory) -> None:
    game = make_game()
    me, enemy = game.bots
    place(me, 20, 100)
    place(enemy, 170, 100)
    me.targeting.target = enemy
    me.weapons.add_weapon(EntityType.RAIL_GUN)
    me.weapons.add_weapon(EntityType.SHOTGUN)
    me.weapons.select_weapon()
    assert me.weapons.current.type is EntityType.RAIL_GUN  # 150 away: closest to 200
    me.targeting.clear()
    me.weapons.select_weapon()
    assert me.weapons.current.type is EntityType.BLASTER  # type: ignore[comparison-overlap]


# --- life and death -------------------------------------------------------------------------------
def test_death_scores_for_the_killer_and_leaves_a_grave(make_game: GameFactory) -> None:
    game = make_game()
    killer, victim = game.bots
    place(killer, 50, 100)
    place(victim, 150, 100)
    game.dispatcher.dispatch(Message.TAKE_THAT_MF, killer.id, victim.id, extra=500)
    assert victim.is_dead
    assert killer.score == 1
    game.update()
    assert victim.is_spawning
    assert len(game.graves.graves) == 1
    game.update()
    assert victim.is_alive
    assert victim.health == victim.max_health


def test_removed_bot_is_forgotten(make_game: GameFactory) -> None:
    game = make_game()
    me, other = game.bots
    place(me, 50, 100)
    place(other, 150, 100)
    me.memory.update_vision()
    me.targeting.update()
    game.remove_bot()
    assert me.targeting.target is None
    assert other not in me.memory.records


def test_possession_by_clicks(make_game: GameFactory) -> None:
    game = make_game(bots=1)  # alone, so nobody shoots or pushes it
    [bot] = game.bots
    place(bot, 50, 100)
    game.click_right(Vector2D(50, 100))
    assert game.selected_bot is bot
    assert not bot.possessed
    game.click_right(Vector2D(50, 100))
    assert bot.possessed
    game.click_right(Vector2D(150, 150))
    for _ in range(300):
        game.update()
    assert bot.is_at_position(Vector2D(150, 150))
    game.exorcise()
    assert not bot.possessed


def test_facing_turns_at_the_head_turn_rate(make_game: GameFactory) -> None:
    game = make_game(bots=1)
    bot = place(game.bots[0], 100, 100, facing=Vector2D(1, 0))
    assert not bot.rotate_facing_toward(Vector2D(100, 150))
    assert bot.facing.is_close(Vector2D(1, 0).rotate(game.params.bot.max_head_turn_rate))
    for _ in range(10):
        bot.rotate_facing_toward(Vector2D(100, 150))
    assert bot.rotate_facing_toward(Vector2D(100, 150))


def test_a_match_on_the_synthetic_map_runs(make_game: GameFactory) -> None:
    game = make_game(bots=3)
    for _ in range(60 * 30):
        game.update()
    assert all(0 <= b.position.x <= 200 and 0 <= b.position.y <= 200 for b in game.bots)


@pytest.mark.skipif(original_map("Raven_DM1.map") is None, reason="original maps not available")
def test_original_maps_load() -> None:
    for name, nodes, walls, doors in (
        ("Raven_DM1.map", 340, 58, 0),
        ("Raven_DM1_With_Doors.map", 29, 64, 3),
    ):
        path = original_map(name)
        assert path is not None
        game = RavenGame(path)
        assert game.map.graph.num_active_nodes == nodes
        assert len(game.map.walls) == walls
        assert len(game.map.doors) == doors
