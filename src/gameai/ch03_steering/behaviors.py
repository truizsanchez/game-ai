"""Combining steering behaviors (C++ ``SteeringBehavior`` class, "Combining Steering Behaviors").

The C++ class repeats one ``if (On(x)) ...`` block per behavior in each of its three
combination methods. Here :meth:`SteeringBehaviors.force_for` computes any single behavior,
and each combination method is a short loop over :data:`PRIORITY`.
"""

from __future__ import annotations

import random
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from gameai.ch03_steering.behaviors_flag import GROUP_BEHAVIORS, PRIORITY, Behavior, Summing
from gameai.common import steering
from gameai.common.steering import Deceleration, Path, WanderState
from gameai.common.vector2d import ZERO, Vector2D

if TYPE_CHECKING:
    from gameai.ch03_steering.vehicle import Vehicle


def accumulate_force(total: Vector2D, force: Vector2D, max_force: float) -> Vector2D | None:
    """Add as much of ``force`` as fits under ``max_force``; None if there was no room left."""
    remaining = max_force - total.length()
    if remaining <= 0:
        return None
    return total + force.truncate(remaining)


@dataclass(eq=False)
class SteeringBehaviors:
    vehicle: Vehicle
    rng: random.Random = field(default_factory=random.Random)
    active: Behavior = Behavior.NONE
    summing: Summing = Summing.PRIORITIZED
    deceleration: Deceleration = Deceleration.NORMAL

    # Behavior-specific data (the C++ m_pTargetAgent1/2, m_vOffset, m_pPath).
    pursuit_target: Vehicle | None = None
    evade_target: Vehicle | None = None
    hide_target: Vehicle | None = None
    interpose_targets: tuple[Vehicle, Vehicle] | None = None
    leader: Vehicle | None = None
    offset: Vector2D = ZERO
    path: Path | None = None
    wander_state: WanderState = field(init=False)

    # Results of the last calculation, kept for rendering.
    force: Vector2D = field(default=ZERO, init=False)
    neighbors: list[Vehicle] = field(default_factory=list, init=False)
    feelers: list[Vector2D] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self.wander_state = WanderState.random(self.rng)
        params = self.vehicle.world.params
        self.weights = dict(params.weights)
        self.probabilities = params.probabilities

    def is_on(self, behavior: Behavior) -> bool:
        return behavior in self.active

    def calculate(self) -> Vector2D:
        """The steering force to apply this update, combined with ``self.summing``."""
        if self.active & GROUP_BEHAVIORS:
            self.neighbors = self._find_neighbors()
        match self.summing:
            case Summing.WEIGHTED_AVERAGE:
                self.force = self._weighted_sum()
            case Summing.PRIORITIZED:
                self.force = self._prioritized()
            case Summing.DITHERED:
                self.force = self._dithered()
        return self.force

    def _active_in_priority_order(self) -> Iterator[Behavior]:
        return (b for b in PRIORITY if b in self.active)

    def _weighted_sum(self) -> Vector2D:
        total = sum(
            (self.force_for(b) * self.weights[b] for b in self._active_in_priority_order()), ZERO
        )
        return total.truncate(self.vehicle.max_force)

    def _prioritized(self) -> Vector2D:
        total = ZERO
        for behavior in self._active_in_priority_order():
            force = self.force_for(behavior) * self.weights[behavior]
            accumulated = accumulate_force(total, force, self.vehicle.max_force)
            if accumulated is None:
                break
            total = accumulated
        return total

    def _dithered(self) -> Vector2D:
        for behavior in self._active_in_priority_order():
            probability = self.probabilities.get(behavior, 1.0)
            if self.rng.random() < probability:
                force = self.force_for(behavior) * self.weights[behavior] / probability
                if force:
                    return force.truncate(self.vehicle.max_force)
        return ZERO

    def _find_neighbors(self) -> list[Vehicle]:
        vehicle = self.vehicle
        ignored = {vehicle, self.evade_target, self.leader, self.pursuit_target}
        found = vehicle.world.neighbors(vehicle.position, vehicle.world.params.view_distance)
        return [v for v in found if v not in ignored]

    def force_for(self, behavior: Behavior) -> Vector2D:
        """The unweighted force of one behavior."""
        vehicle, world = self.vehicle, self.vehicle.world
        match behavior:
            case Behavior.SEEK:
                return steering.seek(vehicle, world.crosshair)
            case Behavior.FLEE:
                return steering.flee(vehicle, world.crosshair)
            case Behavior.ARRIVE:
                return steering.arrive(vehicle, world.crosshair, self.deceleration)
            case Behavior.WANDER:
                return steering.wander(vehicle, self.wander_state, vehicle.time_elapsed, self.rng)
            case Behavior.PURSUIT:
                return steering.pursuit(vehicle, _required(self.pursuit_target, behavior))
            case Behavior.EVADE:
                return steering.evade(vehicle, _required(self.evade_target, behavior))
            case Behavior.HIDE:
                hunter = _required(self.hide_target, behavior)
                return steering.hide(vehicle, hunter, world.obstacles)
            case Behavior.INTERPOSE:
                a, b = _required(self.interpose_targets, behavior)
                return steering.interpose(vehicle, a, b)
            case Behavior.OFFSET_PURSUIT:
                leader = _required(self.leader, behavior)
                return steering.offset_pursuit(vehicle, leader, self.offset)
            case Behavior.FOLLOW_PATH:
                path = _required(self.path, behavior)
                return steering.follow_path(vehicle, path, world.params.waypoint_seek_distance)
            case Behavior.OBSTACLE_AVOIDANCE:
                return steering.obstacle_avoidance(
                    vehicle, world.obstacles, world.params.min_detection_box_length
                )
            case Behavior.WALL_AVOIDANCE:
                length = world.params.wall_detection_feeler_length
                self.feelers = steering.create_feelers(vehicle, length)
                return steering.wall_avoidance(vehicle, world.walls, self.feelers)
            case Behavior.SEPARATION:
                return steering.separation(vehicle, self.neighbors)
            case Behavior.ALIGNMENT:
                return steering.alignment(vehicle, self.neighbors)
            case Behavior.COHESION:
                return steering.cohesion(vehicle, self.neighbors)
        raise ValueError(f"not a single behavior: {behavior}")


def _required[T](value: T | None, behavior: Behavior) -> T:
    if value is None:
        raise RuntimeError(f"{behavior.name} is on but has no target assigned")
    return value
