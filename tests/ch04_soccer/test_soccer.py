import itertools
import random

import pytest

from gameai.ch04_soccer import goalkeeper_states as gks
from gameai.ch04_soccer.ball import SoccerBall
from gameai.ch04_soccer.pitch import SoccerPitch
from gameai.ch04_soccer.players import GoalKeeper, Role
from gameai.ch04_soccer.team_states import DEFENDING_REGIONS, TeamColor
from gameai.common.clock import ManualClock
from gameai.common.geometry import Wall2D, tangent_points
from gameai.common.regulator import Regulator
from gameai.common.vector2d import Vector2D


def ball() -> SoccerBall:
    return SoccerBall(Vector2D(100, 100), 5, mass=1, friction=-0.015)


# --- ball physics -------------------------------------------------------------------------
def test_kick_sets_velocity_from_force_and_mass() -> None:
    b = SoccerBall(Vector2D(0, 0), 5, mass=2, friction=-0.015)
    b.kick(Vector2D(3, 0), 6)
    assert b.velocity == Vector2D(3, 0)


def test_friction_slows_the_ball_until_it_stops() -> None:
    b = ball()
    b.kick(Vector2D(1, 0), 1.0)
    speeds = []
    for _ in range(100):
        b.update([])
        speeds.append(b.speed)
    assert speeds[0] == pytest.approx(1.0 - 0.015)
    assert all(a >= c for a, c in itertools.pairwise(speeds))
    assert speeds[-1] < 0.015


def test_time_to_cover_distance_matches_the_simulation() -> None:
    b = ball()
    start, target = b.position, b.position + Vector2D(30, 0)
    predicted = b.time_to_cover_distance(start, target, 1.0)
    assert predicted is not None
    b.kick(Vector2D(1, 0), 1.0)
    ticks = 0
    while b.position.x < target.x:
        b.update([])
        ticks += 1
    assert ticks == pytest.approx(predicted, abs=1.5)


def test_time_to_cover_distance_is_none_when_the_ball_stops_short() -> None:
    b = ball()
    assert b.time_to_cover_distance(Vector2D(0, 0), Vector2D(1000, 0), 1.0) is None


def test_future_position_matches_the_simulation() -> None:
    b = ball()
    b.kick(Vector2D(1, 1), 2.0)
    predicted = b.future_position(20)
    for _ in range(20):
        b.update([])
    assert b.position.distance(predicted) < 0.5


def test_ball_bounces_off_a_wall() -> None:
    b = ball()
    b.position = Vector2D(100, 26)
    b.velocity = Vector2D(1, -2)
    floor = Wall2D(Vector2D(0, 20), Vector2D(200, 20))  # normal points up
    b.update([floor])
    assert b.velocity.y > 0


# --- pitch --------------------------------------------------------------------------------
@pytest.fixture
def pitch() -> SoccerPitch:
    return SoccerPitch(rng=random.Random(3))


def test_region_numbering_matches_the_original(pitch: SoccerPitch) -> None:
    top_left, bottom_right = pitch.regions[17], pitch.regions[0]
    assert top_left.left == pitch.playing_area.left
    assert top_left.top == pitch.playing_area.top
    assert bottom_right.right == pitch.playing_area.right
    assert bottom_right.bottom == pitch.playing_area.bottom
    assert [r.id for r in pitch.regions] == list(range(18))


def test_region_inside_half_size(pitch: SoccerPitch) -> None:
    region = pitch.regions[7]
    corner_ish = Vector2D(region.left + 2, region.bottom + 2)
    assert region.inside(corner_ish)
    assert not region.inside(corner_ish, half_size=True)
    assert region.inside(region.center, half_size=True)


def test_teams_start_in_their_defending_regions(pitch: SoccerPitch) -> None:
    for team in (pitch.red, pitch.blue):
        regions = [p.home_region for p in team.players]
        assert regions == list(DEFENDING_REGIONS[team.color])
        assert isinstance(team.players[0], GoalKeeper)
        assert [p.role for p in team.players].count(Role.ATTACKER) == 2
        assert all(p.in_home_region() for p in team.players)


def test_walls_face_inwards(pitch: SoccerPitch) -> None:
    center = pitch.playing_area.center
    assert all(wall.normal.dot(center - wall.center) > 0 for wall in pitch.walls)


def test_goal_is_scored_when_the_ball_crosses_the_line(pitch: SoccerPitch) -> None:
    goal = pitch.blue_goal
    assert goal.scored(Vector2D(675, 200), Vector2D(685, 200))
    assert not goal.scored(Vector2D(675, 30), Vector2D(685, 30))  # wide of the posts
    assert pitch.score == (1, 0)


# --- team tactics ---------------------------------------------------------------------------
def test_pass_safety(pitch: SoccerPitch) -> None:
    team, opponent = pitch.red, pitch.blue.players[1]
    start, target = Vector2D(100, 200), Vector2D(300, 200)
    force = pitch.params.max_passing_force
    opponent.position = Vector2D(50, 200)  # behind the kicker
    assert team.is_pass_safe_from_opponent(start, target, None, opponent, force)
    opponent.position = Vector2D(200, 202)  # standing on the ball's path
    assert not team.is_pass_safe_from_opponent(start, target, None, opponent, force)
    opponent.position = Vector2D(200, 380)  # far to the side
    assert team.is_pass_safe_from_opponent(start, target, None, opponent, force)


def test_can_shoot_aims_between_the_posts(pitch: SoccerPitch) -> None:
    for p in pitch.blue.players:  # clear the way
        p.position = Vector2D(100, 30)
    target = pitch.red.can_shoot(Vector2D(600, 200), pitch.params.max_shooting_force)
    assert target is not None
    goal = pitch.blue_goal
    assert target.x == goal.center.x
    assert goal.post_a.y < target.y < goal.post_b.y


def test_find_pass_prefers_the_receiver_nearest_the_opponents_goal(pitch: SoccerPitch) -> None:
    for p in pitch.blue.players:
        p.position = Vector2D(100, 30)
    keeper, *_ = pitch.red.players
    pitch.ball.place_at(keeper.position)
    found = pitch.red.find_pass(keeper, pitch.params.max_passing_force, 50)
    assert found is not None
    receiver, target = found
    assert receiver in pitch.red.players
    others = [p for p in pitch.red.players if p is not keeper and p is not receiver]
    assert all(target.x >= p.position.x - 60 for p in others)


def test_taking_control_takes_it_from_the_opponents(pitch: SoccerPitch) -> None:
    pitch.red.controlling_player = pitch.red.players[1]
    pitch.blue.controlling_player = pitch.blue.players[1]
    assert pitch.blue.in_control
    assert not pitch.red.in_control


def test_keeper_catches_a_nearby_ball(pitch: SoccerPitch) -> None:
    keeper = pitch.red.players[0]
    assert isinstance(keeper, GoalKeeper)
    pitch.ball.place_at(keeper.position + Vector2D(3, 0))
    pitch.update()
    assert pitch.goalkeeper_has_ball
    assert keeper.fsm.is_in_state(gks.PutBallBackInPlay) or keeper.fsm.is_in_state(gks.TendGoal)


def test_closest_player_chases_the_ball(pitch: SoccerPitch) -> None:
    for _ in range(30):
        pitch.update()
    chasers = [p for p in pitch.all_players if p.state_name in {"ChaseBall", "KickBall"}]
    assert chasers
    assert all(p.is_closest_team_member_to_ball() for p in chasers)


def test_regulator_limits_the_rate() -> None:
    clock = ManualClock()
    regulator = Regulator(8, clock, random.Random(0))
    ready = 0
    for _ in range(600):  # 10 seconds at 60 ticks per second
        clock.advance(1 / 60)
        ready += regulator.is_ready()
    # A 0.125 s period rounds up to 8 ticks (7.5/s), and the first update may wait up to 1 s.
    assert 65 <= ready <= 81
    assert Regulator(0, clock).is_ready()
    assert not Regulator(-1, clock).is_ready()


def test_tangent_points_are_perpendicular_to_the_radius() -> None:
    center, point = Vector2D(0, 0), Vector2D(5, 0)
    points = tangent_points(center, 3, point)
    assert points is not None
    for t in points:
        assert t.length() == pytest.approx(3)
        assert (point - t).dot(t - center) == pytest.approx(0)
    assert tangent_points(center, 3, Vector2D(1, 0)) is None


@pytest.mark.parametrize("seed", [1, 2])
def test_a_full_match_is_played_and_reproducible(seed: int) -> None:
    def play() -> tuple[tuple[int, int], Vector2D]:
        pitch = SoccerPitch(rng=random.Random(seed))
        for _ in range(60 * 90):  # a minute and a half
            pitch.update()
        return pitch.score, pitch.ball.position

    first = play()
    assert first == play()


def test_teams_are_red_left_and_blue_right(pitch: SoccerPitch) -> None:
    assert pitch.red.color is TeamColor.RED
    assert pitch.red.home_goal.center.x < pitch.blue.home_goal.center.x
