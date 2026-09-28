"""Game entities (C++ ``Common/Game/BaseGameEntity.h`` and ``MovingEntity.h``)."""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterable
from dataclasses import dataclass, field

from gameai.common.vector2d import UNIT_X, ZERO, Vector2D

_next_id = itertools.count()


@dataclass(eq=False)
class BaseGameEntity:
    """Anything with a position and a bounding circle. Ids are unique per process."""

    position: Vector2D = ZERO
    bounding_radius: float = 0.0
    id: int = field(default_factory=lambda: next(_next_id), kw_only=True)


@dataclass(eq=False)
class MovingEntity(BaseGameEntity):
    """An entity with velocity, a heading and limits on how it can move.

    ``heading`` is kept normalized; ``side`` (its perpendicular) is derived from it, so the
    two can never get out of sync as they can with the C++ member pair.
    """

    velocity: Vector2D = ZERO
    heading: Vector2D = UNIT_X
    mass: float = 1.0
    max_speed: float = 1.0
    max_force: float = 1.0
    max_turn_rate: float = math.pi  # radians per second

    @property
    def side(self) -> Vector2D:
        return self.heading.perp()

    @property
    def speed(self) -> float:
        return self.velocity.length()

    def rotate_heading_to_face(self, target: Vector2D, max_turn: float | None = None) -> bool:
        """Turn towards ``target`` by at most ``max_turn`` (default ``max_turn_rate``) radians.

        Rotates the velocity too. Returns True once the entity faces the target.
        """
        to_target = (target - self.position).normalize()
        angle = self.heading.angle_to(to_target)
        if angle < 1e-5:
            return True
        angle = min(angle, self.max_turn_rate if max_turn is None else max_turn)
        if self.heading.cross(to_target) < 0:
            angle = -angle
        self.heading = self.heading.rotate(angle)
        self.velocity = self.velocity.rotate(angle)
        return False


def enforce_non_penetration(entity: BaseGameEntity, others: Iterable[BaseGameEntity]) -> None:
    """Push ``entity`` out of any entity it overlaps (section "Ensuring Zero Overlap")."""
    for other in others:
        if other is entity:
            continue
        to_entity = entity.position - other.position
        distance = to_entity.length()
        overlap = other.bounding_radius + entity.bounding_radius - distance
        if overlap >= 0 and distance > 0:
            entity.position += to_entity / distance * overlap
