"""Projectiles (C++ ``armory/Raven_Projectile``, ``Projectile_*``; chapter 7 "Projectiles").

Everything moves once per tick. Hits are reported to the victim with a ``TAKE_THAT_MF``
message carrying the damage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Self

from gameai.common.entity import MovingEntity
from gameai.common.geometry import (
    closest_wall_intersection,
    distance_to_segment,
    segment_circle_intersection,
)
from gameai.common.vector2d import ZERO, Vector2D
from gameai.raven.entity_types import Message
from gameai.raven.params import ProjectileParams

if TYPE_CHECKING:
    from gameai.raven.bot import RavenBot
    from gameai.raven.game import RavenGame

TARGET_TOLERANCE = 5.0  # a rocket explodes this close to where it was aimed


@dataclass(eq=False)
class Projectile(MovingEntity):
    world: RavenGame = field(kw_only=True)
    shooter_id: int = field(kw_only=True)
    target: Vector2D = field(kw_only=True)
    damage: int = field(kw_only=True)
    origin: Vector2D = field(default=ZERO, init=False)
    dead: bool = field(default=False, init=False)
    impacted: bool = field(default=False, init=False)
    impact_point: Vector2D = field(default=ZERO, init=False)
    time_of_creation: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        self.origin = self.position
        self.time_of_creation = self.world.clock()

    @classmethod
    def fired_by(
        cls, shooter: RavenBot, target: Vector2D, params: ProjectileParams, **extra: Any
    ) -> Self:
        """A projectile leaving the shooter along its facing direction."""
        return cls(
            shooter.position,
            shooter.world.params.bot.scale,
            heading=shooter.facing,
            max_speed=params.max_speed,
            mass=params.mass,
            max_force=params.max_force,
            world=shooter.world,
            shooter_id=shooter.id,
            target=target,
            damage=params.damage,
            **extra,
        )

    def update(self) -> None:
        raise NotImplementedError

    # --- helpers -------------------------------------------------------------------------------
    def _victims(self, start: Vector2D, end: Vector2D) -> list[RavenBot]:
        """Living bots (other than the shooter) whose bounding circle the segment touches."""
        return [
            bot
            for bot in self.world.bots
            if bot.is_alive
            and bot.id != self.shooter_id
            and distance_to_segment(start, end, bot.position) < bot.bounding_radius
        ]

    def _closest_victim(self, start: Vector2D, end: Vector2D) -> RavenBot | None:
        return min(
            self._victims(start, end),
            key=lambda bot: bot.position.distance_sq(self.origin),
            default=None,
        )

    def _hit(self, bot: RavenBot) -> None:
        self.world.dispatcher.dispatch(
            Message.TAKE_THAT_MF, self.shooter_id, bot.id, extra=self.damage
        )

    def _move_straight(self) -> tuple[Vector2D, Vector2D]:
        """Advance along the heading at full speed; return the segment travelled."""
        self.velocity = self.heading * self.max_speed
        start = self.position
        self.position += self.velocity
        return start, self.position


@dataclass(eq=False)
class Bolt(Projectile):
    """The blaster's slow bolt of energy."""

    def update(self) -> None:
        if self.impacted:
            return
        start, end = self._move_straight()
        if victim := self._closest_victim(start, end):
            self.impacted = self.dead = True
            self._hit(victim)
            return
        if wall_hit := closest_wall_intersection(start, end, self.world.map.walls):
            self.impacted = self.dead = True
            self.position = self.impact_point = wall_hit.point


@dataclass(eq=False)
class Rocket(Projectile):
    """Explodes on hitting a bot, a wall or its target, damaging everyone in the blast."""

    blast_radius: float = field(default=20.0, kw_only=True)
    explosion_decay_rate: float = field(default=2.0, kw_only=True)
    current_blast_radius: float = field(default=0.0, init=False)

    def update(self) -> None:
        if self.impacted:
            self.current_blast_radius += self.explosion_decay_rate
            if self.current_blast_radius > self.blast_radius:
                self.dead = True
            return
        start, end = self._move_straight()
        if victim := self._closest_victim(start, end):
            self._hit(victim)
            self._explode()
        elif wall_hit := closest_wall_intersection(start, end, self.world.map.walls):
            self.position = wall_hit.point
            self._explode()
        elif self.position.distance_sq(self.target) < TARGET_TOLERANCE**2:
            self._explode()

    def _explode(self) -> None:
        self.impacted = True
        self.impact_point = self.position
        for bot in self.world.bots:
            if bot.is_alive and self.position.distance(bot.position) < (
                self.blast_radius + bot.bounding_radius
            ):
                self._hit(bot)


@dataclass(eq=False)
class Slug(Projectile):
    """The rail gun's instant-hit slug: goes through bots (hitting them all) until a wall."""

    persistance: float = field(default=0.2, kw_only=True)

    def update(self) -> None:
        if self.impacted:
            self.dead = self.world.clock() - self.time_of_creation > self.persistance
            return
        self.impacted = True
        wall_hit = closest_wall_intersection(self.origin, self.target, self.world.map.walls)
        self.impact_point = wall_hit.point if wall_hit else self.target
        self.position = self.impact_point
        for bot in self._victims(self.origin, self.impact_point):
            self._hit(bot)


@dataclass(eq=False)
class Pellet(Projectile):
    """One shotgun pellet: instant hit on the first bot or wall in its way."""

    persistance: float = field(default=0.1, kw_only=True)

    def update(self) -> None:
        if self.impacted:
            self.dead = self.world.clock() - self.time_of_creation > self.persistance
            return
        self.impacted = True
        wall_hit = closest_wall_intersection(self.origin, self.target, self.world.map.walls)
        self.impact_point = wall_hit.point if wall_hit else self.target
        if victim := self._closest_victim(self.origin, self.impact_point):
            entry = segment_circle_intersection(
                self.origin, self.impact_point, victim.position, victim.bounding_radius
            )
            self.impact_point = entry or victim.position
            self._hit(victim)
        self.position = self.impact_point
