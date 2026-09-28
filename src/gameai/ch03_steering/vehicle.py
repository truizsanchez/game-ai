"""The vehicle model (C++ ``Vehicle``, section "The Vehicle Model")."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from gameai.ch03_steering.behaviors import SteeringBehaviors
from gameai.common.entity import MovingEntity
from gameai.common.smoother import Smoother
from gameai.common.vector2d import ZERO, Vector2D, wrap_around

if TYPE_CHECKING:
    from gameai.ch03_steering.world import GameWorld

# Outline in local space (heading along +x), multiplied by the bounding radius when drawn.
SHAPE = (Vector2D(-1.0, 0.6), Vector2D(1.0, 0.0), Vector2D(-1.0, -0.6))


@dataclass(eq=False)
class Vehicle(MovingEntity):
    world: GameWorld = field(kw_only=True)
    smoothing: bool = field(default=False, kw_only=True)
    steering: SteeringBehaviors = field(init=False)
    smoothed_heading: Vector2D = field(default=ZERO, init=False)
    time_elapsed: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        self.steering = SteeringBehaviors(self, rng=self.world.rng)
        self._heading_smoother = Smoother(self.world.params.num_samples_for_smoothing, ZERO)

    def update(self, dt: float) -> None:
        """Integrate the steering force (section "Updating the Vehicle Physics")."""
        self.time_elapsed = dt
        acceleration = self.steering.calculate() / self.mass
        self.velocity = (self.velocity + acceleration * dt).truncate(self.max_speed)
        self.position += self.velocity * dt
        if self.velocity.length_sq() > 1e-8:
            self.heading = self.velocity.normalize()
        self.position = wrap_around(self.position, self.world.width, self.world.height)
        self.world.cell_space.update(self)
        if self.smoothing:
            self.smoothed_heading = self._heading_smoother.update(self.heading)

    @property
    def display_heading(self) -> Vector2D:
        """The heading to draw: smoothed when smoothing is on (section "Smoothing")."""
        return self.smoothed_heading.normalize() if self.smoothing else self.heading
