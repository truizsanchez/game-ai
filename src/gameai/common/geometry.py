"""2D geometry tests (C++ ``Common/2D/geometry.h``, ``Wall2D.h``), ported as chapters need them."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

from gameai.common.vector2d import Vector2D


class Intersection(NamedTuple):
    distance: float  # along the first segment, from its start
    point: Vector2D


def segment_intersection(a: Vector2D, b: Vector2D, c: Vector2D, d: Vector2D) -> Intersection | None:
    """Where segment AB crosses segment CD (excluding the end points), or None."""
    ab, cd, ca = b - a, d - c, a - c
    denominator = ab.cross(cd)
    if denominator == 0:  # parallel
        return None
    r = cd.cross(ca) / denominator  # position along AB
    s = ab.cross(ca) / denominator  # position along CD
    if 0 < r < 1 and 0 < s < 1:
        return Intersection(ab.length() * r, a + ab * r)
    return None


def circles_overlap(c1: Vector2D, r1: float, c2: Vector2D, r2: float) -> bool:
    return c1.distance_sq(c2) < (r1 + r2) ** 2


def point_in_circle(center: Vector2D, radius: float, point: Vector2D) -> bool:
    return center.distance_sq(point) < radius * radius


@dataclass(frozen=True, slots=True)
class Wall2D:
    """A wall segment. Its normal points to the left of ``start → end`` (y axis up)."""

    start: Vector2D
    end: Vector2D

    @property
    def normal(self) -> Vector2D:
        return (self.end - self.start).normalize().perp()

    @property
    def center(self) -> Vector2D:
        return (self.start + self.end) / 2


def walls_from_polygon(vertices: list[Vector2D]) -> list[Wall2D]:
    """Close a polygon into walls. List the vertices anticlockwise for inward normals."""
    return [Wall2D(a, b) for a, b in zip(vertices, vertices[1:] + vertices[:1], strict=True)]
