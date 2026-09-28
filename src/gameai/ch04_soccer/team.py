"""A soccer team (C++ ``SoccerTeam``, sections "The SoccerTeam Class" and "Key Methods")."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from gameai.ch04_soccer import field_player_states as fps
from gameai.ch04_soccer import team_states
from gameai.ch04_soccer.messages import Message
from gameai.ch04_soccer.players import FieldPlayer, GoalKeeper, PlayerBase, Role
from gameai.ch04_soccer.support_spots import SupportSpotCalculator
from gameai.ch04_soccer.team_states import DEFENDING_REGIONS, TeamColor
from gameai.common.fsm import StateMachine
from gameai.common.geometry import tangent_points
from gameai.common.transformations import point_to_local_space
from gameai.common.vector2d import Vector2D

if TYPE_CHECKING:
    from gameai.ch04_soccer.pitch import SoccerPitch
    from gameai.ch04_soccer.pitch_geometry import Goal

INTERCEPT_SCALING = 0.3  # how far a receiver is assumed to move to meet a pass
PASS_REQUEST_CHANCE = 0.1


ROLES = (Role.GOALKEEPER, Role.ATTACKER, Role.ATTACKER, Role.DEFENDER, Role.DEFENDER)


@dataclass(eq=False)
class SoccerTeam:
    color: TeamColor
    home_goal: Goal
    opponents_goal: Goal
    pitch: SoccerPitch
    opponents: SoccerTeam = field(init=False)
    players: list[PlayerBase] = field(default_factory=list, init=False)
    _controlling_player: PlayerBase | None = field(default=None, init=False)
    supporting_player: PlayerBase | None = field(default=None, init=False)
    receiver: PlayerBase | None = field(default=None, init=False)
    player_closest_to_ball: PlayerBase | None = field(default=None, init=False)
    closest_dist_sq_to_ball: float = field(default=float("inf"), init=False)
    fsm: StateMachine[SoccerTeam] = field(init=False)

    def __post_init__(self) -> None:
        self.fsm = StateMachine(self, current=team_states.DEFENDING)
        self.fsm.previous = team_states.DEFENDING
        params = self.pitch.params
        self.support_spots = SupportSpotCalculator(
            self, params.num_support_spots_x, params.num_support_spots_y
        )

    def create_players(self) -> None:
        """Five players in their defending home regions, facing up or down the pitch."""
        params = self.pitch.params
        heading = Vector2D(0, -1) if self.color is TeamColor.BLUE else Vector2D(0, 1)
        for region, role in zip(DEFENDING_REGIONS[self.color], ROLES, strict=True):
            cls = GoalKeeper if role is Role.GOALKEEPER else FieldPlayer
            player = cls(
                self.pitch.regions[region].center,
                10.0 * params.player_scale,
                heading=heading,
                mass=params.player_mass,
                max_force=params.player_max_force,
                max_speed=params.player_max_speed_without_ball,
                max_turn_rate=params.player_max_turn_rate,
                team=self,
                home_region=region,
                role=role,
            )
            self.players.append(player)
            self.pitch.entities.register(player)

    # --- per-tick bookkeeping -------------------------------------------------------------
    def update(self) -> None:
        self.calculate_closest_player_to_ball()
        self.fsm.update()
        for player in self.players:
            player.update()

    def calculate_closest_player_to_ball(self) -> None:
        ball = self.pitch.ball.position
        for player in self.players:
            player.dist_sq_to_ball = player.position.distance_sq(ball)
        closest = min(self.players, key=lambda p: p.dist_sq_to_ball)
        self.player_closest_to_ball = closest
        self.closest_dist_sq_to_ball = closest.dist_sq_to_ball

    # --- control ---------------------------------------------------------------------------
    @property
    def controlling_player(self) -> PlayerBase | None:
        return self._controlling_player

    @controlling_player.setter
    def controlling_player(self, player: PlayerBase | None) -> None:
        """Taking control means the opponents lose it."""
        self._controlling_player = player
        if player is not None:
            self.opponents._controlling_player = None

    @property
    def in_control(self) -> bool:
        return self._controlling_player is not None

    def set_home_regions(self, regions: tuple[int, ...]) -> None:
        for player, region in zip(self.players, regions, strict=True):
            player.home_region = region

    def update_targets_of_waiting_players(self) -> None:
        for player in self.players:
            if isinstance(player, FieldPlayer) and (
                player.fsm.is_in_state(fps.Wait) or player.fsm.is_in_state(fps.ReturnToHomeRegion)
            ):
                player.steering.target = player.home.center

    def all_players_at_home(self) -> bool:
        return all(player.in_home_region() for player in self.players)

    def return_all_field_players_home(self) -> None:
        for player in self.players:
            if player.role is not Role.GOALKEEPER:
                self.pitch.dispatcher.dispatch(Message.GO_HOME, -1, player.id)

    # --- support ---------------------------------------------------------------------------
    def support_spot(self) -> Vector2D:
        return self.support_spots.best_spot()

    def determine_best_supporting_attacker(self) -> PlayerBase | None:
        spot = self.support_spot()
        attackers = [
            p for p in self.players if p.role is Role.ATTACKER and p is not self.controlling_player
        ]
        return min(attackers, key=lambda p: p.position.distance_sq(spot), default=None)

    def request_pass(self, requester: FieldPlayer) -> None:
        """Occasionally ask the controlling player for the ball, if the pass would be safe."""
        controller = self.controlling_player
        if controller is None or self.pitch.rng.random() > PASS_REQUEST_CHANCE:
            return
        force = self.pitch.params.max_passing_force
        if self.is_pass_safe_from_all_opponents(
            controller.position, requester.position, requester, force
        ):
            self.pitch.dispatcher.dispatch(
                Message.PASS_TO_ME, requester.id, controller.id, extra=requester
            )

    def is_opponent_within_radius(self, position: Vector2D, radius: float) -> bool:
        return any(
            position.distance_sq(opp.position) < radius * radius for opp in self.opponents.players
        )

    # --- passing and shooting ----------------------------------------------------------------
    def find_pass(
        self, passer: PlayerBase, power: float, min_distance: float
    ) -> tuple[PlayerBase, Vector2D] | None:
        """The safe pass to a teammate that lands closest to the opponents' goal."""
        best: tuple[float, PlayerBase, Vector2D] | None = None
        for receiver in self.players:
            if receiver is passer or passer.position.distance_sq(receiver.position) <= (
                min_distance**2
            ):
                continue
            target = self.best_pass_to_receiver(receiver, power)
            if target is None:
                continue
            to_goal = abs(target.x - self.opponents_goal.center.x)
            if best is None or to_goal < best[0]:
                best = (to_goal, receiver, target)
        return None if best is None else (best[1], best[2])

    def best_pass_to_receiver(self, receiver: PlayerBase, power: float) -> Vector2D | None:
        """Try passing to the receiver's feet and to either side of it (tangent points)."""
        ball = self.pitch.ball
        time = ball.time_to_cover_distance(ball.position, receiver.position, power)
        if time is None:
            return None
        intercept_range = time * receiver.max_speed * INTERCEPT_SCALING
        tangents = tangent_points(receiver.position, intercept_range, ball.position)
        candidates = [receiver.position]
        if tangents is not None:
            candidates = [tangents[0], receiver.position, tangents[1]]
        safe = [
            target
            for target in candidates
            if self.pitch.playing_area.inside(target)
            and self.is_pass_safe_from_all_opponents(ball.position, target, receiver, power)
        ]
        return min(safe, key=lambda t: abs(t.x - self.opponents_goal.center.x), default=None)

    def is_pass_safe_from_opponent(
        self,
        start: Vector2D,
        target: Vector2D,
        receiver: PlayerBase | None,
        opponent: PlayerBase,
        force: float,
    ) -> bool:
        """Can ``opponent`` reach the ball's path before the ball passes it?"""
        direction = (target - start).normalize()
        local = point_to_local_space(opponent.position, direction, direction.perp(), start)
        if local.x < 0:
            return True  # behind the kicker
        if start.distance_sq(target) < start.distance_sq(opponent.position):
            # The opponent is further away than the target: safe if the receiver gets there first.
            return receiver is None or target.distance_sq(opponent.position) > target.distance_sq(
                receiver.position
            )
        ball = self.pitch.ball
        time = ball.time_to_cover_distance(Vector2D(), Vector2D(local.x, 0), force)
        if time is None:
            return False  # the ball stops before passing the opponent
        reach = opponent.max_speed * time + ball.bounding_radius + opponent.bounding_radius
        return abs(local.y) >= reach

    def is_pass_safe_from_all_opponents(
        self, start: Vector2D, target: Vector2D, receiver: PlayerBase | None, force: float
    ) -> bool:
        return all(
            self.is_pass_safe_from_opponent(start, target, receiver, opp, force)
            for opp in self.opponents.players
        )

    def can_shoot(self, ball_position: Vector2D, power: float) -> Vector2D | None:
        """A random point in the goal mouth that a shot from here would reach safely."""
        goal, ball, rng = self.opponents_goal, self.pitch.ball, self.pitch.rng
        low = min(goal.post_a.y, goal.post_b.y) + ball.bounding_radius
        high = max(goal.post_a.y, goal.post_b.y) - ball.bounding_radius
        for _ in range(self.pitch.params.num_attempts_to_find_valid_strike):
            target = Vector2D(goal.center.x, rng.uniform(low, high))
            if ball.time_to_cover_distance(
                ball_position, target, power
            ) is not None and self.is_pass_safe_from_all_opponents(
                ball_position, target, None, power
            ):
                return target
        return None
