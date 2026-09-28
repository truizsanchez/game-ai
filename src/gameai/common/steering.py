"""Steering behaviors as pure functions (C++ ``SteeringBehaviors.cpp``, chapter 3).

Each behavior takes the ``agent`` it steers plus whatever it reacts to, and returns a
steering force. None of them mutates anything, except :func:`follow_path` (advances the
path) — state such as the wander target is passed in and returned by the caller. Chapter 3
combines them in ``gameai.ch03_steering.behaviors``; later chapters reuse them directly.
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import IntEnum

from gameai.common.entity import BaseGameEntity, MovingEntity
from gameai.common.geometry import Wall2D, segment_intersection
from gameai.common.transformations import (
    point_to_local_space,
    point_to_world_space,
    vector_to_world_space,
)
from gameai.common.utils import random_clamped
from gameai.common.vector2d import ZERO, Vector2D


class Deceleration(IntEnum):
    """How gently ``arrive`` slows down: the larger, the earlier it starts braking."""

    SLOW = 3
    NORMAL = 2
    FAST = 1


DECELERATION_TWEAKER = 0.3
EVADE_THREAT_RANGE = 100.0
HIDE_DISTANCE_FROM_BOUNDARY = 30.0
OBSTACLE_BRAKING_WEIGHT = 0.2


# --- individual behaviors -------------------------------------------------------------
def seek(agent: MovingEntity, target: Vector2D) -> Vector2D:
    desired_velocity = (target - agent.position).normalize() * agent.max_speed
    return desired_velocity - agent.velocity


def flee(agent: MovingEntity, target: Vector2D, panic_distance: float | None = None) -> Vector2D:
    """Head away from ``target``; if ``panic_distance`` is given, only when that close."""
    if panic_distance is not None and agent.position.distance_sq(target) > panic_distance**2:
        return ZERO
    desired_velocity = (agent.position - target).normalize() * agent.max_speed
    return desired_velocity - agent.velocity


def arrive(
    agent: MovingEntity, target: Vector2D, deceleration: Deceleration = Deceleration.NORMAL
) -> Vector2D:
    """Like seek, but slowing down to stop exactly at ``target``."""
    to_target = target - agent.position
    distance = to_target.length()
    if distance <= 0:
        return ZERO
    speed = min(distance / (deceleration * DECELERATION_TWEAKER), agent.max_speed)
    desired_velocity = to_target * (speed / distance)
    return desired_velocity - agent.velocity


def pursuit(agent: MovingEntity, evader: MovingEntity) -> Vector2D:
    """Seek where the evader will be, predicted from the distance between them."""
    to_evader = evader.position - agent.position
    relative_heading = agent.heading.dot(evader.heading)
    # Evader ahead and facing us (within ~18 degrees): just seek its current position.
    if to_evader.dot(agent.heading) > 0 and relative_heading < -0.95:
        return seek(agent, evader.position)
    look_ahead = to_evader.length() / (agent.max_speed + evader.speed)
    return seek(agent, evader.position + evader.velocity * look_ahead)


def evade(
    agent: MovingEntity, pursuer: MovingEntity, threat_range: float = EVADE_THREAT_RANGE
) -> Vector2D:
    """Flee from where the pursuer will be, if it is within ``threat_range``."""
    to_pursuer = pursuer.position - agent.position
    if to_pursuer.length_sq() > threat_range * threat_range:
        return ZERO
    look_ahead = to_pursuer.length() / (agent.max_speed + pursuer.speed)
    return flee(agent, pursuer.position + pursuer.velocity * look_ahead)


@dataclass
class WanderState:
    """The wander circle, in units of the agent's bounding radius, and the target on it."""

    radius: float = 1.2
    distance: float = 2.0
    jitter: float = 80.0  # per second
    target: Vector2D = field(default=ZERO)

    @classmethod
    def random(cls, rng: random.Random | None = None) -> WanderState:
        state = cls()
        state.target = Vector2D.from_angle((rng or random).random() * math.tau, state.radius)
        return state


def wander(
    agent: MovingEntity, state: WanderState, dt: float, rng: random.Random | None = None
) -> Vector2D:
    """Jitter a target around a circle projected in front of the agent and head for it.

    Updates ``state.target``: the target's position on the circle is what makes the motion
    smooth from one update to the next.
    """
    jitter = state.jitter * dt
    moved = state.target + Vector2D(random_clamped(rng) * jitter, random_clamped(rng) * jitter)
    state.target = moved.normalize() * state.radius
    local_target = (state.target + Vector2D(state.distance, 0)) * agent.bounding_radius
    world_target = point_to_world_space(local_target, agent.heading, agent.side, agent.position)
    return world_target - agent.position


def detection_box_length(agent: MovingEntity, min_length: float) -> float:
    """Obstacle-avoidance look-ahead: grows with speed, from 1x to 2x ``min_length``."""
    return min_length + (agent.speed / agent.max_speed) * min_length


def obstacle_avoidance(
    agent: MovingEntity, obstacles: Iterable[BaseGameEntity], min_box_length: float
) -> Vector2D:
    """Steer away from the closest obstacle intersecting the detection box ahead."""
    box_length = detection_box_length(agent, min_box_length)
    closest_ip = math.inf
    closest: tuple[BaseGameEntity, Vector2D] | None = None
    for obstacle in obstacles:
        reach = box_length + obstacle.bounding_radius
        if obstacle.position.distance_sq(agent.position) >= reach * reach:
            continue
        local = point_to_local_space(obstacle.position, agent.heading, agent.side, agent.position)
        expanded_radius = obstacle.bounding_radius + agent.bounding_radius
        if local.x < 0 or abs(local.y) >= expanded_radius:
            continue  # behind the agent, or clear of the box sideways
        # Intersection of the circle with the local x axis: x = cx ± sqrt(r² - cy²).
        sqrt_part = math.sqrt(expanded_radius**2 - local.y**2)
        ip = local.x - sqrt_part
        if ip <= 0:
            ip = local.x + sqrt_part
        if ip < closest_ip:
            closest_ip, closest = ip, (obstacle, local)

    if closest is None:
        return ZERO
    obstacle, local = closest
    # The closer the obstacle, the stronger the lateral push; plus a little braking.
    multiplier = 1.0 + (box_length - local.x) / box_length
    # The book uses (obstacle radius - local.y), which for an obstacle slightly to the left
    # (0 < y < radius) pushes *towards* it. Push away from the obstacle's side instead, harder
    # the more centered it is.
    expanded_radius = obstacle.bounding_radius + agent.bounding_radius
    away = -1.0 if local.y > 0 else 1.0
    lateral = away * (expanded_radius - abs(local.y)) * multiplier
    braking = (obstacle.bounding_radius - local.x) * OBSTACLE_BRAKING_WEIGHT
    return vector_to_world_space(Vector2D(braking, lateral), agent.heading, agent.side)


def create_feelers(agent: MovingEntity, length: float) -> list[Vector2D]:
    """Three whiskers: one straight ahead and two half-length ones at ±45 degrees."""
    ahead = agent.position + agent.heading * length
    right = agent.position + agent.heading.rotate(-math.pi / 4) * (length / 2)
    left = agent.position + agent.heading.rotate(math.pi / 4) * (length / 2)
    return [ahead, right, left]


def wall_avoidance(
    agent: MovingEntity, walls: Sequence[Wall2D], feelers: Sequence[Vector2D]
) -> Vector2D:
    """Push along the normal of the wall hit closest to the agent, by the feeler's overshoot."""
    closest = min(
        (
            (hit.distance, feeler, hit.point, wall)
            for feeler in feelers
            for wall in walls
            if (hit := segment_intersection(agent.position, feeler, wall.start, wall.end))
        ),
        default=None,
        key=lambda candidate: candidate[0],
    )
    if closest is None:
        return ZERO
    _, feeler, point, wall = closest
    return wall.normal * (feeler - point).length()


def separation(agent: MovingEntity, neighbors: Iterable[MovingEntity]) -> Vector2D:
    """Push away from each neighbor, inversely proportional to its distance."""
    fx = fy = 0.0
    for other in neighbors:
        dx, dy = agent.position.x - other.position.x, agent.position.y - other.position.y
        distance_sq = dx * dx + dy * dy
        if distance_sq > 0:  # to_agent.normalize() / distance == to_agent / distance²
            fx += dx / distance_sq
            fy += dy / distance_sq
    return Vector2D(fx, fy)


def alignment(agent: MovingEntity, neighbors: Sequence[MovingEntity]) -> Vector2D:
    """Steer towards the neighbors' average heading."""
    if not neighbors:
        return ZERO
    average = sum((n.heading for n in neighbors), ZERO) / len(neighbors)
    return average - agent.heading


def cohesion(agent: MovingEntity, neighbors: Sequence[MovingEntity]) -> Vector2D:
    """Seek the neighbors' center of mass (normalized, as in the C++ code)."""
    if not neighbors:
        return ZERO
    center = sum((n.position for n in neighbors), ZERO) / len(neighbors)
    return seek(agent, center).normalize()


def interpose(agent: MovingEntity, a: MovingEntity, b: MovingEntity) -> Vector2D:
    """Arrive at the point between ``a`` and ``b``, predicting where they will be."""
    midpoint = (a.position + b.position) / 2
    time_to_midpoint = agent.position.distance(midpoint) / agent.max_speed
    future_a = a.position + a.velocity * time_to_midpoint
    future_b = b.position + b.velocity * time_to_midpoint
    return arrive(agent, (future_a + future_b) / 2, Deceleration.FAST)


def hiding_position(obstacle: BaseGameEntity, hunter_position: Vector2D) -> Vector2D:
    """The spot just behind ``obstacle`` as seen from the hunter."""
    distance_away = obstacle.bounding_radius + HIDE_DISTANCE_FROM_BOUNDARY
    to_obstacle = (obstacle.position - hunter_position).normalize()
    return obstacle.position + to_obstacle * distance_away


def hide(
    agent: MovingEntity, hunter: MovingEntity, obstacles: Iterable[BaseGameEntity]
) -> Vector2D:
    """Arrive at the nearest hiding spot, or evade if there is nowhere to hide."""
    spots = [hiding_position(obstacle, hunter.position) for obstacle in obstacles]
    if not spots:
        return evade(agent, hunter)
    best = min(spots, key=agent.position.distance_sq)
    return arrive(agent, best, Deceleration.FAST)


def offset_pursuit(agent: MovingEntity, leader: MovingEntity, offset: Vector2D) -> Vector2D:
    """Keep station at ``offset`` (in the leader's local space), e.g. in a formation."""
    target = point_to_world_space(offset, leader.heading, leader.side, leader.position)
    look_ahead = (target - agent.position).length() / (agent.max_speed + leader.speed)
    return arrive(agent, target + leader.velocity * look_ahead, Deceleration.FAST)


@dataclass
class Path:
    """Waypoints to follow, optionally looping back to the first."""

    waypoints: list[Vector2D]
    looped: bool = False
    current_index: int = 0

    @property
    def current(self) -> Vector2D:
        return self.waypoints[self.current_index]

    @property
    def finished(self) -> bool:
        """True when heading for the last waypoint of a non-looped path."""
        return not self.looped and self.current_index == len(self.waypoints) - 1

    def advance(self) -> None:
        if self.current_index < len(self.waypoints) - 1:
            self.current_index += 1
        elif self.looped:
            self.current_index = 0

    @classmethod
    def random(
        cls,
        count: int,
        lower_left: Vector2D,
        upper_right: Vector2D,
        looped: bool = True,
        rng: random.Random | None = None,
    ) -> Path:
        """``count`` waypoints spread around the center of the box, at random distances."""
        r = rng or random
        center = (lower_left + upper_right) / 2
        max_radius = min(center.x - lower_left.x, center.y - lower_left.y)
        spacing = math.tau / count
        return cls(
            [
                center + Vector2D.from_angle(i * spacing, r.uniform(max_radius * 0.2, max_radius))
                for i in range(count)
            ],
            looped,
        )


def follow_path(agent: MovingEntity, path: Path, waypoint_seek_distance: float) -> Vector2D:
    """Seek each waypoint in turn, switching when close enough; arrive at the last one."""
    if path.current.distance_sq(agent.position) < waypoint_seek_distance**2:
        path.advance()
    if path.finished:
        return arrive(agent, path.current, Deceleration.NORMAL)
    return seek(agent, path.current)
