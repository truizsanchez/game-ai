"""Physics of motion from chapter 1: constant acceleration equations and force-driven bodies."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from gameai.common.vector2d import ZERO, Vector2D


def final_velocity(u: float, a: float, t: float) -> float:
    """v = u + at (eq. 1.81)."""
    return u + a * t


def displacement(u: float, a: float, t: float) -> float:
    """Δx = uΔt + ½aΔt² (eq. 1.87)."""
    return u * t + 0.5 * a * t * t


def velocity_after_distance(u: float, a: float, dx: float) -> float:
    """v = √(u² + 2aΔx) (eq. 1.91): speed after covering ``dx`` without knowing the time."""
    return math.sqrt(u * u + 2 * a * dx)


def angle_to_face(position: Vector2D, heading: Vector2D, target: Vector2D) -> float:
    """Radians an agent must turn to face ``target`` (the troll and princess example).

    θ = cos⁻¹(N_TP · H) (eq. 1.74), with ``heading`` already normalized.
    """
    return heading.angle_to(target - position)


def is_ahead(position: Vector2D, heading: Vector2D, target: Vector2D) -> bool:
    """True if ``target`` is in front of the agent's facing plane (dot product > 0)."""
    return heading.dot(target - position) > 0


@dataclass
class Body:
    """A point mass moved by forces: the book's ``SpaceShip`` (and ``Vehicle``, with no force).

    ``update`` integrates acceleration into velocity and then velocity into position, in that
    order (semi-implicit Euler), exactly as the book's listing does.
    """

    mass: float
    position: Vector2D = ZERO
    velocity: Vector2D = ZERO
    acceleration: Vector2D = field(default=ZERO, init=False)

    def update(self, dt: float, force: Vector2D = ZERO) -> None:
        self.acceleration = force / self.mass  # a = F/m (eq. 1.93)
        self.velocity += self.acceleration * dt  # from eq. 1.80
        self.position += self.velocity * dt  # from eq. 1.77
