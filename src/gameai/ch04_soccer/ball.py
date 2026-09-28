"""The soccer ball (C++ ``SoccerBall``, section "The Soccer Ball")."""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass, field

from gameai.common.entity import MovingEntity
from gameai.common.geometry import Wall2D
from gameai.common.utils import random_clamped
from gameai.common.vector2d import ZERO, Vector2D


@dataclass(eq=False)
class SoccerBall(MovingEntity):
    """A ball slowed by constant friction. Time is measured in ticks."""

    friction: float = field(default=-0.015, kw_only=True)  # negative: it decelerates
    old_position: Vector2D = field(default=ZERO, init=False)

    def __post_init__(self) -> None:
        self.old_position = self.position

    def kick(self, direction: Vector2D, force: float) -> None:
        """Set the ball's velocity: the kick is an instantaneous impulse."""
        self.velocity = direction.normalize() * force / self.mass

    def trap(self) -> None:
        self.velocity = ZERO

    def place_at(self, position: Vector2D) -> None:
        self.position = self.old_position = position
        self.velocity = ZERO

    def update(self, walls: Sequence[Wall2D]) -> None:
        self.old_position = self.position
        self.bounce_off_walls(walls)
        # Stop once friction would reverse the ball rather than slow it.
        if self.velocity.length_sq() > self.friction**2:
            self.velocity += self.velocity.normalize() * self.friction
            self.position += self.velocity
            self.heading = self.velocity.normalize()

    def bounce_off_walls(self, walls: Sequence[Wall2D]) -> None:
        """Reflect the velocity off the nearest wall the ball will reach this tick."""
        closest: tuple[float, Wall2D] | None = None
        for wall in walls:
            normal = wall.normal
            approach = -self.velocity.dot(normal)
            if approach <= 0:
                continue  # moving parallel to or away from the wall
            gap = (self.position - wall.start).dot(normal) - self.bounding_radius
            along = (self.position - wall.start).dot(wall.end - wall.start)
            within_segment = 0 <= along <= (wall.end - wall.start).length_sq()
            reaches_wall = gap <= approach  # within this tick's travel towards it
            if within_segment and reaches_wall and (closest is None or gap < closest[0]):
                closest = (gap, wall)
        if closest is not None:
            self.velocity = self.velocity.reflect(closest[1].normal)

    def future_position(self, time: float) -> Vector2D:
        """Where the ball will be after ``time`` ticks: Δx = ut + ½at² (section 1)."""
        u_t = self.velocity * time
        half_a_t_sq = 0.5 * self.friction * time * time
        return self.position + u_t + self.velocity.normalize() * half_a_t_sq

    def time_to_cover_distance(self, a: Vector2D, b: Vector2D, force: float) -> float | None:
        """Ticks for a ball kicked with ``force`` to travel from ``a`` to ``b``; None if never.

        From v² = u² + 2aΔx: if the term is negative the ball stops before reaching ``b``.
        """
        speed = force / self.mass
        term = speed * speed + 2.0 * a.distance(b) * self.friction
        if term <= 0:
            return None
        return (math.sqrt(term) - speed) / self.friction


def add_noise_to_kick(
    ball_position: Vector2D, target: Vector2D, accuracy: float, rng: random.Random
) -> Vector2D:
    """Rotate the kick direction by up to ±π·(1 - accuracy) radians: players aren't perfect."""
    displacement = (math.pi - math.pi * accuracy) * random_clamped(rng)
    return ball_position + (target - ball_position).rotate(displacement)
