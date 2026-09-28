"""2D geometry tests (C++ ``Common/2D/geometry.h``, ``Wall2D.h``), ported as chapters need them."""

from __future__ import annotations

import math
from collections.abc import Iterable
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


def tangent_points(
    center: Vector2D, radius: float, point: Vector2D
) -> tuple[Vector2D, Vector2D] | None:
    """The two points where lines from ``point`` touch the circle, or None if it's inside."""
    to_point = point - center
    dist_sq = to_point.length_sq()
    if dist_sq <= radius * radius:
        return None
    root = math.sqrt(dist_sq - radius * radius)
    k = radius / dist_sq
    rx, ry = radius * to_point.x, radius * to_point.y
    t1 = center + Vector2D(rx - to_point.y * root, ry + to_point.x * root) * k
    t2 = center + Vector2D(rx + to_point.y * root, ry - to_point.x * root) * k
    return t1, t2


def distance_to_segment(a: Vector2D, b: Vector2D, p: Vector2D) -> float:
    """Distance from point ``p`` to the segment AB."""
    ab = b - a
    length_sq = ab.length_sq()
    if length_sq == 0:
        return p.distance(a)
    t = max(0.0, min(1.0, (p - a).dot(ab) / length_sq))
    return p.distance(a + ab * t)


def segment_circle_intersection(
    a: Vector2D, b: Vector2D, center: Vector2D, radius: float
) -> Vector2D | None:
    """The point where segment AB first enters the circle, or None if it misses it."""
    ab = b - a
    length = ab.length()
    if length == 0:
        return None
    direction = ab / length
    to_center = center - a
    along = to_center.dot(direction)  # position of the closest approach along AB
    offset_sq = to_center.length_sq() - along * along
    if offset_sq >= radius * radius:
        return None
    half_chord = math.sqrt(radius * radius - offset_sq)
    entry = along - half_chord
    if entry < 0:
        entry = along + half_chord  # A is inside the circle: use the exit point
    if not 0 <= entry <= length:
        return None
    return a + direction * entry


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


# --- wall tests (C++ Common/2D/WallIntersectionTests.h) ------------------------------------
def walls_obstruct_segment(a: Vector2D, b: Vector2D, walls: Iterable[Wall2D]) -> bool:
    """True if the segment AB crosses any wall: no line of sight between A and B."""
    return any(segment_intersection(a, b, w.start, w.end) is not None for w in walls)


def walls_intersect_circle(walls: Iterable[Wall2D], center: Vector2D, radius: float) -> bool:
    return any(distance_to_segment(w.start, w.end, center) < radius for w in walls)


def closest_wall_intersection(
    a: Vector2D, b: Vector2D, walls: Iterable[Wall2D]
) -> Intersection | None:
    """The first point where AB hits a wall, going from A to B."""
    hits = (segment_intersection(a, b, w.start, w.end) for w in walls)
    return min((h for h in hits if h is not None), key=lambda h: h.distance, default=None)
