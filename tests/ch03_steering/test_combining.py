import random

import pytest

from gameai.ch03_steering.behaviors import accumulate_force
from gameai.ch03_steering.behaviors_flag import PRIORITY, Behavior, Summing
from gameai.ch03_steering.params import load
from gameai.ch03_steering.world import GameWorld
from gameai.common.vector2d import Vector2D


@pytest.fixture
def world() -> GameWorld:
    return GameWorld(800, 600, rng=random.Random(0))


def test_params_apply_the_force_tweaker() -> None:
    params = load()
    assert params.max_steering_force == 2.0 * 200
    assert params.weights[Behavior.EVADE] == pytest.approx(0.01 * 200)
    assert params.probabilities[Behavior.WANDER] == 0.8
    assert set(params.weights) == set(PRIORITY)


def test_accumulate_force_caps_the_total() -> None:
    total = accumulate_force(Vector2D(3, 0), Vector2D(10, 0), max_force=5)
    assert total == Vector2D(5, 0)
    assert accumulate_force(Vector2D(5, 0), Vector2D(1, 0), max_force=5) is None


def seek_and_flee(world: GameWorld, summing: Summing) -> Vector2D:
    """A vehicle both seeking and fleeing the same crosshair: the two forces cancel out."""
    world.crosshair = Vector2D(500, 300)
    v = world.add_vehicle(Vector2D(400, 300))
    v.steering.active = Behavior.SEEK | Behavior.FLEE
    v.steering.summing = summing
    return v.steering.calculate()


def test_weighted_sum_adds_everything(world: GameWorld) -> None:
    assert seek_and_flee(world, Summing.WEIGHTED_AVERAGE).is_close(Vector2D())


def test_prioritized_lets_higher_priority_use_up_the_budget(world: GameWorld) -> None:
    # Flee comes before seek in PRIORITY and alone reaches max_force, so seek gets nothing.
    force = seek_and_flee(world, Summing.PRIORITIZED)
    assert force.is_close(Vector2D(-world.params.max_steering_force, 0))


def test_dithered_picks_one_behavior(world: GameWorld) -> None:
    force = seek_and_flee(world, Summing.DITHERED)
    assert force.length() == pytest.approx(world.params.max_steering_force)


def test_missing_target_is_an_error(world: GameWorld) -> None:
    v = world.add_vehicle()
    v.steering.active = Behavior.PURSUIT
    with pytest.raises(RuntimeError, match="PURSUIT"):
        v.steering.calculate()


def test_neighbors_exclude_self_and_the_evade_target(world: GameWorld) -> None:
    shark = world.add_vehicle(Vector2D(100, 100))
    fish = world.add_vehicle(Vector2D(105, 100))
    friend = world.add_vehicle(Vector2D(110, 100))
    fish.steering.active = Behavior.SEPARATION | Behavior.EVADE
    fish.steering.evade_target = shark
    fish.steering.calculate()
    assert fish.steering.neighbors == [friend]


@pytest.mark.parametrize("partitioning", [True, False])
def test_partitioning_does_not_change_neighbors(world: GameWorld, partitioning: bool) -> None:
    for _ in range(100):
        world.add_vehicle()
    world.space_partitioning = partitioning
    probe = world.vehicles[0].position
    expected = {v for v in world.vehicles if v.position.distance_sq(probe) < 50**2}
    assert set(world.neighbors(probe, 50)) == expected


def test_vehicles_stay_inside_the_walls(world: GameWorld) -> None:
    world.create_walls()
    for _ in range(15):
        v = world.add_vehicle(Vector2D(world.rng.uniform(250, 550), world.rng.uniform(200, 400)))
        v.steering.active = Behavior.WANDER | Behavior.WALL_AVOIDANCE
    for _ in range(60 * 20):  # 20 simulated seconds
        world.update(1 / 60)
    assert all(20 <= v.position.x <= 780 and 20 <= v.position.y <= 580 for v in world.vehicles)


def test_vehicles_rarely_touch_obstacles(world: GameWorld) -> None:
    world.create_obstacles()
    for _ in range(10):
        v = world.add_vehicle(max_speed=100)
        v.steering.active = Behavior.WANDER | Behavior.OBSTACLE_AVOIDANCE
    touching = 0
    for _ in range(60 * 10):
        world.update(1 / 60)
        touching += sum(
            v.position.distance(o.position) < o.bounding_radius
            for v in world.vehicles
            for o in world.obstacles
        )
    # Vehicles wrap around the screen edges and may reappear inside an obstacle, so a few
    # contacts are expected; without avoidance there are hundreds.
    assert touching < 60
