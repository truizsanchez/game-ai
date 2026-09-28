"""World space <-> local space conversions (C++ ``Common/2D/Transformations.h``).

An agent's local coordinate system has its origin at the agent's position, the x axis along
its (normalized) ``heading`` and the y axis along its ``side`` (``heading.perp()``, the agent's
left). The C++ code builds a matrix for every conversion; here the local/world conversions are
written directly as the dot products and linear combinations that the matrix encodes.
"""

from __future__ import annotations

from collections.abc import Iterable

from gameai.common.matrix2d import Matrix2D
from gameai.common.vector2d import Vector2D


def world_transform(
    points: Iterable[Vector2D],
    position: Vector2D,
    heading: Vector2D,
    side: Vector2D,
    scale: Vector2D | None = None,
) -> list[Vector2D]:
    """Place a shape defined in local space (e.g. a vehicle's outline) into the world."""
    matrix = Matrix2D.rotation_from(heading, side) @ Matrix2D.translation(position.x, position.y)
    if scale is not None:
        matrix = Matrix2D.scaling(scale.x, scale.y) @ matrix
    return matrix.transform_all(points)


def point_to_world_space(
    point: Vector2D, heading: Vector2D, side: Vector2D, position: Vector2D
) -> Vector2D:
    return position + vector_to_world_space(point, heading, side)


def vector_to_world_space(vector: Vector2D, heading: Vector2D, side: Vector2D) -> Vector2D:
    """Rotate a direction from local to world space (no translation: vectors have no position)."""
    return heading * vector.x + side * vector.y


def point_to_local_space(
    point: Vector2D, heading: Vector2D, side: Vector2D, position: Vector2D
) -> Vector2D:
    return vector_to_local_space(point - position, heading, side)


def vector_to_local_space(vector: Vector2D, heading: Vector2D, side: Vector2D) -> Vector2D:
    """Project a world direction onto the agent's axes."""
    return Vector2D(vector.dot(heading), vector.dot(side))
