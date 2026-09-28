"""Simple Soccer's own steering (C++ ``SteeringBehaviors`` in the SimpleSoccer project).

A small subset of chapter 3, always combined by prioritized accumulation, with two
ball-specific variants: pursuit of the ball's predicted position and interposing between
the ball and a target.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Flag, auto
from typing import TYPE_CHECKING

from gameai.common import steering
from gameai.common.steering import Deceleration
from gameai.common.vector2d import ZERO, Vector2D

if TYPE_CHECKING:
    from gameai.ch04_soccer.players import PlayerBase


class Behavior(Flag):
    NONE = 0
    SEEK = auto()
    ARRIVE = auto()
    SEPARATION = auto()
    PURSUIT = auto()
    INTERPOSE = auto()


@dataclass(eq=False)
class SoccerSteering:
    player: PlayerBase
    active: Behavior = Behavior.NONE
    target: Vector2D = ZERO
    interpose_distance: float = 0.0
    force: Vector2D = field(default=ZERO, init=False)

    def is_on(self, behavior: Behavior) -> bool:
        return behavior in self.active

    def turn_on(self, behavior: Behavior) -> None:
        self.active |= behavior

    def turn_off(self, behavior: Behavior) -> None:
        self.active &= ~behavior

    def calculate(self) -> Vector2D:
        """Prioritized accumulation: separation, seek, arrive, pursuit, interpose."""
        player = self.player
        total = ZERO
        for behavior in (
            Behavior.SEPARATION,
            Behavior.SEEK,
            Behavior.ARRIVE,
            Behavior.PURSUIT,
            Behavior.INTERPOSE,
        ):
            if behavior not in self.active:
                continue
            remaining = player.max_force - total.length()
            if remaining <= 0:
                break
            total += self._force_for(behavior).truncate(remaining)
        self.force = total.truncate(player.max_force)
        return self.force

    def _force_for(self, behavior: Behavior) -> Vector2D:
        player, ball = self.player, self.player.ball
        match behavior:
            case Behavior.SEPARATION:
                params = player.pitch.params
                neighbors = [
                    other
                    for other in player.pitch.all_players
                    if other is not player
                    and other.position.distance_sq(player.position) < params.view_distance**2
                ]
                return steering.separation(player, neighbors) * params.separation_coefficient
            case Behavior.SEEK:
                return steering.seek(player, self.target)
            case Behavior.ARRIVE:
                return steering.arrive(player, self.target, Deceleration.FAST)
            case Behavior.PURSUIT:
                # Head for where the ball will be when we could get there.
                look_ahead = (
                    ball.position.distance(player.position) / ball.speed if ball.speed else 0
                )
                self.target = ball.future_position(look_ahead)
                return steering.arrive(player, self.target, Deceleration.FAST)
            case Behavior.INTERPOSE:
                # Stay between the ball and the target, interpose_distance from the target.
                towards_ball = (ball.position - self.target).normalize()
                point = self.target + towards_ball * self.interpose_distance
                return steering.arrive(player, point, Deceleration.NORMAL)
        raise ValueError(f"not a single behavior: {behavior}")

    def forward_component(self) -> float:
        return self.player.heading.dot(self.force)

    def side_component(self) -> float:
        return self.player.side.dot(self.force) * self.player.max_turn_rate
