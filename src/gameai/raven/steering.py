"""Raven's steering (C++ ``Raven_SteeringBehaviors``): a subset of chapter 3, per tick.

Prioritized in this order: wall avoidance, separation, seek, arrive, wander.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Flag, auto
from typing import TYPE_CHECKING

from gameai.common import steering
from gameai.common.steering import Deceleration, WanderState
from gameai.common.vector2d import ZERO, Vector2D

if TYPE_CHECKING:
    from gameai.raven.bot import RavenBot

WANDER_JITTER_PER_TICK = 40.0


class Behavior(Flag):
    NONE = 0
    SEEK = auto()
    ARRIVE = auto()
    WANDER = auto()
    SEPARATION = auto()
    WALL_AVOIDANCE = auto()


PRIORITY = (
    Behavior.WALL_AVOIDANCE,
    Behavior.SEPARATION,
    Behavior.SEEK,
    Behavior.ARRIVE,
    Behavior.WANDER,
)


@dataclass(eq=False)
class RavenSteering:
    bot: RavenBot
    active: Behavior = Behavior.NONE
    target: Vector2D = ZERO
    deceleration: Deceleration = Deceleration.NORMAL
    force: Vector2D = field(default=ZERO, init=False)
    feelers: list[Vector2D] = field(default_factory=list, init=False)
    wander_state: WanderState = field(init=False)

    def __post_init__(self) -> None:
        self.wander_state = WanderState.random(self.bot.world.rng)
        self.wander_state.jitter = WANDER_JITTER_PER_TICK

    def is_on(self, behavior: Behavior) -> bool:
        return behavior in self.active

    def turn_on(self, behavior: Behavior) -> None:
        self.active |= behavior

    def turn_off(self, behavior: Behavior) -> None:
        self.active &= ~behavior

    def calculate(self) -> Vector2D:
        total = ZERO
        for behavior in PRIORITY:
            if behavior not in self.active:
                continue
            remaining = self.bot.max_force - total.length()
            if remaining <= 0:
                break
            total += self._weighted_force(behavior).truncate(remaining)
        self.force = total
        return total

    def _weighted_force(self, behavior: Behavior) -> Vector2D:
        bot, weights = self.bot, self.bot.world.params.steering
        match behavior:
            case Behavior.WALL_AVOIDANCE:
                self.feelers = self.create_feelers()
                force = steering.wall_avoidance(bot, bot.world.map.walls, self.feelers)
                return force * weights.wall_avoidance_weight
            case Behavior.SEPARATION:
                view_sq = weights.view_distance**2
                neighbors = [
                    b
                    for b in bot.world.bots
                    if b is not bot
                    and b.is_alive
                    and b.position.distance_sq(bot.position) < view_sq
                ]
                return steering.separation(bot, neighbors) * weights.separation_weight
            case Behavior.SEEK:
                return steering.seek(bot, self.target) * weights.seek_weight
            case Behavior.ARRIVE:
                return steering.arrive(bot, self.target, self.deceleration) * weights.arrive_weight
            case Behavior.WANDER:
                force = steering.wander(bot, self.wander_state, 1.0, bot.world.rng)
                return force * weights.wander_weight
        raise ValueError(f"not a single behavior: {behavior}")

    def create_feelers(self) -> list[Vector2D]:
        """Like chapter 3's, but the front feeler grows with speed (``Raven_Steering``)."""
        bot = self.bot
        length = bot.world.params.steering.wall_detection_feeler_length
        return [
            bot.position + bot.heading * (length * bot.speed),
            bot.position + bot.heading.rotate(-math.pi / 4) * (length / 2),
            bot.position + bot.heading.rotate(math.pi / 4) * (length / 2),
        ]
