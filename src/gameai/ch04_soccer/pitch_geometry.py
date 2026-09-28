"""Regions and goals (C++ ``Common/Game/Region.h`` and ``Goal.h``)."""

from __future__ import annotations

import random
from dataclasses import dataclass

from gameai.common.geometry import segment_intersection
from gameai.common.vector2d import Vector2D


@dataclass(frozen=True)
class Region:
    """An axis-aligned rectangle (y axis up)."""

    left: float
    bottom: float
    right: float
    top: float
    id: int = -1

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.top - self.bottom

    @property
    def center(self) -> Vector2D:
        return Vector2D((self.left + self.right) / 2, (self.bottom + self.top) / 2)

    @property
    def length(self) -> float:
        return max(self.width, self.height)

    def inside(self, pos: Vector2D, *, half_size: bool = False) -> bool:
        """Strictly inside; ``half_size`` shrinks the region by a quarter on every side."""
        mx, my = (self.width * 0.25, self.height * 0.25) if half_size else (0.0, 0.0)
        return self.left + mx < pos.x < self.right - mx and self.bottom + my < pos.y < self.top - my

    def random_position(self, rng: random.Random) -> Vector2D:
        return Vector2D(rng.uniform(self.left, self.right), rng.uniform(self.bottom, self.top))


@dataclass
class Goal:
    """A goal mouth between two posts, facing into the pitch."""

    post_a: Vector2D
    post_b: Vector2D
    facing: Vector2D
    goals_scored: int = 0

    @property
    def center(self) -> Vector2D:
        return (self.post_a + self.post_b) / 2

    def scored(self, old_position: Vector2D, new_position: Vector2D) -> bool:
        """True (and counted) if the ball crossed the goal line between the posts."""
        if segment_intersection(new_position, old_position, self.post_a, self.post_b) is None:
            return False
        self.goals_scored += 1
        return True
