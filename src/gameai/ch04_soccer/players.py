"""Players (C++ ``PlayerBase``, ``FieldPlayer``, ``GoalKeeper``)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

from gameai.ch04_soccer import field_player_states as fps
from gameai.ch04_soccer import goalkeeper_states as gks
from gameai.ch04_soccer.messages import Message
from gameai.ch04_soccer.steering import Behavior, SoccerSteering
from gameai.common.entity import MovingEntity, enforce_non_penetration
from gameai.common.fsm import StateMachine
from gameai.common.messaging import Telegram
from gameai.common.regulator import Regulator
from gameai.common.utils import clamp
from gameai.common.vector2d import ZERO, Vector2D

if TYPE_CHECKING:
    from gameai.ch04_soccer.ball import SoccerBall
    from gameai.ch04_soccer.pitch import SoccerPitch
    from gameai.ch04_soccer.pitch_geometry import Region
    from gameai.ch04_soccer.team import SoccerTeam

BRAKING_RATE = 0.8  # velocity multiplier when a field player has no steering force


class Role(Enum):
    GOALKEEPER = auto()
    ATTACKER = auto()
    DEFENDER = auto()


@dataclass(eq=False)
class PlayerBase(MovingEntity):
    team: SoccerTeam = field(kw_only=True)
    home_region: int = field(kw_only=True)
    role: Role = field(kw_only=True)
    default_region: int = field(init=False)
    steering: SoccerSteering = field(init=False)
    dist_sq_to_ball: float = field(default=float("inf"), init=False)

    def __post_init__(self) -> None:
        self.default_region = self.home_region
        self.steering = SoccerSteering(self, active=Behavior.SEPARATION)
        self.steering.target = self.home.center

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.team.color.name} #{self.id})"

    # --- shortcuts ---------------------------------------------------------------------
    @property
    def pitch(self) -> SoccerPitch:
        return self.team.pitch

    @property
    def ball(self) -> SoccerBall:
        return self.team.pitch.ball

    @property
    def home(self) -> Region:
        return self.pitch.regions[self.home_region]

    def dispatch(self, msg: Message, receiver: PlayerBase, extra: object = None) -> None:
        self.pitch.dispatcher.dispatch(msg, self.id, receiver.id, extra=extra)

    # --- questions the states ask ------------------------------------------------------
    def is_ahead(self, position: Vector2D) -> bool:
        """True if ``position`` is in front of the player (``PositionInFrontOfPlayer``)."""
        return (position - self.position).dot(self.heading) > 0

    def is_threatened(self) -> bool:
        """An opponent in front of the player and inside its comfort zone."""
        comfort_sq = self.pitch.params.player_comfort_zone**2
        return any(
            self.is_ahead(opp.position) and self.position.distance_sq(opp.position) < comfort_sq
            for opp in self.team.opponents.players
        )

    @property
    def dist_to_opponents_goal(self) -> float:
        return abs(self.position.x - self.team.opponents_goal.center.x)

    @property
    def dist_to_home_goal(self) -> float:
        return abs(self.position.x - self.team.home_goal.center.x)

    @property
    def is_controlling_player(self) -> bool:
        return self.team.controlling_player is self

    def _ball_within(self, distance: float) -> bool:
        return self.position.distance_sq(self.ball.position) < distance * distance

    def ball_within_keeper_range(self) -> bool:
        return self._ball_within(self.pitch.params.keeper_in_ball_range)

    def ball_within_receiving_range(self) -> bool:
        return self._ball_within(self.pitch.params.ball_within_receiving_range)

    def ball_within_kicking_range(self) -> bool:
        return self._ball_within(self.pitch.params.player_kicking_distance)

    def in_home_region(self) -> bool:
        return self.home.inside(self.position, half_size=self.role is not Role.GOALKEEPER)

    def at_target(self) -> bool:
        target_range = self.pitch.params.player_in_target_range
        return self.position.distance_sq(self.steering.target) < target_range**2

    def is_closest_team_member_to_ball(self) -> bool:
        return self.team.player_closest_to_ball is self

    def is_closest_player_on_pitch_to_ball(self) -> bool:
        return (
            self.is_closest_team_member_to_ball()
            and self.dist_sq_to_ball < self.team.opponents.closest_dist_sq_to_ball
        )

    def in_hot_region(self) -> bool:
        """In the third of the pitch nearest the opponents' goal."""
        return self.dist_to_opponents_goal < self.pitch.playing_area.length / 3

    def is_ahead_of_attacker(self) -> bool:
        attacker = self.team.controlling_player
        assert attacker is not None
        return self.dist_to_opponents_goal < attacker.dist_to_opponents_goal

    # --- actions ------------------------------------------------------------------------
    def track_ball(self) -> None:
        self.rotate_heading_to_face(self.ball.position)

    def find_support(self) -> None:
        """Make sure the best-placed attacker is supporting (``PlayerBase::FindSupport``)."""
        team = self.team
        best = team.determine_best_supporting_attacker()
        if best is None or best is team.supporting_player:
            return
        if team.supporting_player is not None:
            self.dispatch(Message.GO_HOME, team.supporting_player)
        team.supporting_player = best
        self.dispatch(Message.SUPPORT_ATTACKER, best)

    @property
    def state_name(self) -> str:
        raise NotImplementedError

    def update(self) -> None:
        raise NotImplementedError

    def handle_message(self, telegram: Telegram) -> bool:
        raise NotImplementedError


@dataclass(eq=False)
class FieldPlayer(PlayerBase):
    fsm: StateMachine[FieldPlayer] = field(init=False)
    kick_limiter: Regulator = field(init=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        pitch = self.pitch
        self.kick_limiter = Regulator(pitch.params.player_kick_frequency, pitch.clock, pitch.rng)
        self.fsm = StateMachine(self, current=fps.WAIT, global_state=fps.GLOBAL_PLAYER_STATE)
        self.fsm.previous = fps.WAIT
        self.fsm.current.enter(self)

    def is_ready_for_next_kick(self) -> bool:
        return self.kick_limiter.is_ready()

    def update(self) -> None:
        """Turn towards the steering force, limited by the turn rate, then accelerate forward."""
        self.fsm.update()
        steering = self.steering
        steering.calculate()
        if not steering.force:
            self.velocity *= BRAKING_RATE
        turn = clamp(steering.side_component(), -self.max_turn_rate, self.max_turn_rate)
        self.heading = self.heading.rotate(turn)
        self.velocity = self.heading * self.velocity.length()
        acceleration = self.heading * (steering.forward_component() / self.mass)
        self.velocity = (self.velocity + acceleration).truncate(self.max_speed)
        self.position += self.velocity
        if self.pitch.params.non_penetration_constraint:
            enforce_non_penetration(self, self.pitch.all_players)

    def handle_message(self, telegram: Telegram) -> bool:
        return self.fsm.handle_message(telegram)

    @property
    def state_name(self) -> str:
        return self.fsm.current.name


@dataclass(eq=False)
class GoalKeeper(PlayerBase):
    fsm: StateMachine[GoalKeeper] = field(init=False)
    look_at: Vector2D = field(default=ZERO, init=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        self.fsm = StateMachine(self, current=gks.TEND_GOAL, global_state=gks.GLOBAL_KEEPER_STATE)
        self.fsm.previous = gks.TEND_GOAL
        self.fsm.current.enter(self)

    def update(self) -> None:
        self.fsm.update()
        acceleration = self.steering.calculate() / self.mass
        self.velocity = (self.velocity + acceleration).truncate(self.max_speed)
        self.position += self.velocity
        if self.pitch.params.non_penetration_constraint:
            enforce_non_penetration(self, self.pitch.all_players)
        if self.velocity:
            self.heading = self.velocity.normalize()
        if not self.pitch.goalkeeper_has_ball:
            self.look_at = (self.ball.position - self.position).normalize()

    def ball_within_range_for_intercept(self) -> bool:
        intercept = self.pitch.params.goalkeeper_intercept_range
        return self.team.home_goal.center.distance_sq(self.ball.position) <= intercept**2

    def too_far_from_goal_mouth(self) -> bool:
        intercept = self.pitch.params.goalkeeper_intercept_range
        return self.position.distance_sq(self.rear_interpose_target()) > intercept**2

    def rear_interpose_target(self) -> Vector2D:
        """A point on the goal line that tracks the ball's height across the goal mouth."""
        area, goal_width = self.pitch.playing_area, self.pitch.params.goal_width
        fraction = (self.ball.position.y - area.bottom) / area.height
        y = area.center.y - goal_width / 2 + fraction * goal_width
        return Vector2D(self.team.home_goal.center.x, y)

    def handle_message(self, telegram: Telegram) -> bool:
        return self.fsm.handle_message(telegram)

    @property
    def state_name(self) -> str:
        return self.fsm.current.name
