import math
import random

import pytest

from gameai.common import steering
from gameai.common.entity import BaseGameEntity, MovingEntity
from gameai.common.geometry import Wall2D
from gameai.common.steering import Deceleration, Path, WanderState
from gameai.common.vector2d import ZERO, Vector2D


def agent(
    *,
    x: float = 0,
    y: float = 0,
    vx: float = 0,
    vy: float = 0,
    heading: Vector2D = Vector2D(1, 0),  # noqa: B008
    max_speed: float = 10,
    radius: float = 1,
) -> MovingEntity:
    return MovingEntity(
        Vector2D(x, y),
        radius,
        velocity=Vector2D(vx, vy),
        heading=heading,
        max_speed=max_speed,
    )


def test_seek_and_flee_from_rest() -> None:
    a = agent()
    assert steering.seek(a, Vector2D(5, 0)) == Vector2D(10, 0)
    assert steering.flee(a, Vector2D(5, 0)) == Vector2D(-10, 0)


def test_seek_subtracts_current_velocity() -> None:
    assert steering.seek(agent(vx=10), Vector2D(5, 0)) == ZERO  # already at max speed


def test_flee_ignores_targets_beyond_panic_distance() -> None:
    assert steering.flee(agent(), Vector2D(50, 0), panic_distance=20) == ZERO
    assert steering.flee(agent(), Vector2D(10, 0), panic_distance=20)


def test_arrive_slows_down_near_the_target() -> None:
    a = agent()
    assert steering.arrive(a, Vector2D(0, 0)) == ZERO
    # speed = distance / (deceleration * 0.3), capped at max_speed
    near = steering.arrive(a, Vector2D(3, 0), Deceleration.NORMAL)
    assert near.is_close(Vector2D(3 / 0.6, 0))
    far = steering.arrive(a, Vector2D(100, 0), Deceleration.SLOW)
    assert far == Vector2D(10, 0)


def test_pursuit_seeks_current_position_when_head_on() -> None:
    hunter = agent()
    evader = agent(x=10, vx=-5, heading=Vector2D(-1, 0))
    assert steering.pursuit(hunter, evader) == steering.seek(hunter, evader.position)


def test_pursuit_leads_a_crossing_target() -> None:
    hunter = agent()
    evader = agent(x=10, vy=5, heading=Vector2D(0, 1), max_speed=5)
    force = steering.pursuit(hunter, evader)
    assert force.y > 0  # aims ahead of where the evader is now


def test_evade_ignores_distant_pursuers() -> None:
    assert steering.evade(agent(), agent(x=200)) == ZERO
    assert steering.evade(agent(), agent(x=50)).x < 0


def test_wander_target_stays_on_the_circle() -> None:
    a = agent(radius=2)
    state = WanderState.random(random.Random(1))
    for _ in range(20):
        force = steering.wander(a, state, 1 / 60, random.Random(2))
        assert state.target.length() == pytest.approx(state.radius)
    # The target lies ahead of the agent: distance ± radius, in bounding radii.
    assert (state.distance - state.radius) * 2 <= force.x <= (state.distance + state.radius) * 2


def test_obstacle_avoidance_steers_away_from_an_obstacle_ahead() -> None:
    a = agent(radius=1)
    left_of_path = BaseGameEntity(Vector2D(20, 1), 3)
    force = steering.obstacle_avoidance(a, [left_of_path], min_box_length=40)
    assert force.y < 0  # pushed to the right
    assert force.x < 0  # and braking


@pytest.mark.parametrize(
    "obstacle",
    [
        BaseGameEntity(Vector2D(-20, 0), 3),  # behind
        BaseGameEntity(Vector2D(20, 10), 3),  # clear of the box sideways
        BaseGameEntity(Vector2D(100, 0), 3),  # beyond the detection box
    ],
)
def test_obstacle_avoidance_ignores_obstacles_out_of_the_box(obstacle: BaseGameEntity) -> None:
    assert steering.obstacle_avoidance(agent(), [obstacle], min_box_length=40) == ZERO


def test_wall_avoidance_pushes_along_the_wall_normal() -> None:
    a = agent()
    wall = Wall2D(Vector2D(10, -10), Vector2D(10, 10))  # normal points back at the agent
    feelers = steering.create_feelers(a, 40)
    force = steering.wall_avoidance(a, [wall], feelers)
    assert force.is_close(Vector2D(-30, 0))  # the straight feeler overshoots by 30
    assert steering.wall_avoidance(a, [], feelers) == ZERO


def test_create_feelers() -> None:
    ahead, right, left = steering.create_feelers(agent(), 40)
    assert ahead == Vector2D(40, 0)
    assert right.y < 0 < left.y
    assert right.length() == pytest.approx(20)


def test_group_behaviors() -> None:
    a = agent()
    left, right = agent(x=-2, heading=Vector2D(0, 1)), agent(x=4, heading=Vector2D(0, 1))
    assert steering.separation(a, [left, right]).is_close(Vector2D(1 / 2 - 1 / 4, 0))
    assert steering.alignment(a, [left, right]).is_close(Vector2D(-1, 1))
    assert steering.cohesion(a, [left, right]).is_close(Vector2D(1, 0))
    assert steering.alignment(a, []) == steering.cohesion(a, []) == ZERO


def test_interpose_heads_for_the_midpoint() -> None:
    force = steering.interpose(agent(y=-10), agent(x=-10), agent(x=10))
    assert force.x == pytest.approx(0)
    assert force.y > 0


def test_hide_behind_the_nearest_obstacle() -> None:
    hider, hunter = agent(x=50), agent(x=0)
    near, far = BaseGameEntity(Vector2D(40, 0), 5), BaseGameEntity(Vector2D(-100, 0), 5)
    spot = steering.hiding_position(near, hunter.position)
    assert spot == Vector2D(40 + 5 + steering.HIDE_DISTANCE_FROM_BOUNDARY, 0)
    assert steering.hide(hider, hunter, [near, far]) == steering.arrive(
        hider, spot, Deceleration.FAST
    )


def test_hide_evades_when_there_is_nowhere_to_hide() -> None:
    hider, hunter = agent(x=50), agent(x=0)
    assert steering.hide(hider, hunter, []) == steering.evade(hider, hunter)


def test_offset_pursuit_targets_the_offset_in_leader_space() -> None:
    leader = agent(x=100, heading=Vector2D(0, 1))
    follower = agent(x=100, y=-50)
    force = steering.offset_pursuit(follower, leader, Vector2D(-10, 0))  # 10 behind
    assert force.x == pytest.approx(0)
    assert force.y > 0


def test_path_following() -> None:
    path = Path([Vector2D(0, 0), Vector2D(100, 0), Vector2D(100, 100)])
    a = agent()
    steering.follow_path(a, path, waypoint_seek_distance=5)
    assert path.current == Vector2D(100, 0)
    assert not path.finished
    path.advance()
    assert path.finished
    assert steering.follow_path(a, path, 5) == steering.arrive(a, Vector2D(100, 100))
    path.advance()  # stays on the last waypoint
    assert path.current == Vector2D(100, 100)


def test_looped_path_wraps_around() -> None:
    path = Path([Vector2D(0, 0), Vector2D(1, 0)], looped=True)
    path.advance()
    path.advance()
    assert path.current_index == 0
    assert not path.finished


def test_random_path_stays_in_the_box() -> None:
    path = Path.random(6, Vector2D(0, 0), Vector2D(200, 100), rng=random.Random(3))
    assert len(path.waypoints) == 6
    assert all(0 <= p.x <= 200 and 0 <= p.y <= 100 for p in path.waypoints)


def test_rotate_heading_to_face() -> None:
    a = agent(heading=Vector2D(1, 0))
    a.max_turn_rate = math.pi / 4
    assert not a.rotate_heading_to_face(Vector2D(0, 10))
    assert a.heading.is_close(Vector2D.from_angle(math.pi / 4))
    assert not a.rotate_heading_to_face(Vector2D(0, 10))
    assert a.rotate_heading_to_face(Vector2D(0, 10))
