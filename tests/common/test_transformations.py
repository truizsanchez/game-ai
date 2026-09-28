import math

import pytest

from gameai.common.matrix2d import Matrix2D
from gameai.common.transformations import (
    point_to_local_space,
    point_to_world_space,
    vector_to_local_space,
    vector_to_world_space,
    world_transform,
)
from gameai.common.vector2d import Vector2D

# An agent at (10, 10) facing north: its side (left) vector points west.
POSITION = Vector2D(10, 10)
HEADING = Vector2D(0, 1)
SIDE = HEADING.perp()


def test_matrix_composition_reads_left_to_right() -> None:
    p = Vector2D(1, 1)
    scale_then_move = Matrix2D.scaling(2, 2) @ Matrix2D.translation(10, 0)
    move_then_scale = Matrix2D.translation(10, 0) @ Matrix2D.scaling(2, 2)
    assert scale_then_move.transform(p) == Vector2D(12, 2)
    assert move_then_scale.transform(p) == Vector2D(22, 2)


def test_matrix_rotation_is_anticlockwise() -> None:
    assert Matrix2D.rotation(math.pi / 2).transform(Vector2D(1, 0)).is_close(Vector2D(0, 1))
    assert (Matrix2D.identity() @ Matrix2D.identity()) == Matrix2D.identity()


@pytest.mark.parametrize(
    ("world", "local"),
    [
        (Vector2D(10, 20), Vector2D(10, 0)),  # straight ahead
        (Vector2D(0, 10), Vector2D(0, 10)),  # to the left
        (Vector2D(10, 0), Vector2D(-10, 0)),  # behind
    ],
)
def test_point_local_world_round_trip(world: Vector2D, local: Vector2D) -> None:
    assert point_to_local_space(world, HEADING, SIDE, POSITION).is_close(local)
    assert point_to_world_space(local, HEADING, SIDE, POSITION).is_close(world)


def test_vectors_ignore_position() -> None:
    assert vector_to_local_space(Vector2D(0, 5), HEADING, SIDE).is_close(Vector2D(5, 0))
    assert vector_to_world_space(Vector2D(5, 0), HEADING, SIDE).is_close(Vector2D(0, 5))


def test_world_transform_matches_point_to_world_space() -> None:
    shape = [Vector2D(1, 0), Vector2D(-1, 1), Vector2D(-1, -1)]
    placed = world_transform(shape, POSITION, HEADING, SIDE)
    expected = [point_to_world_space(p, HEADING, SIDE, POSITION) for p in shape]
    assert all(a.is_close(b) for a, b in zip(placed, expected, strict=True))


def test_world_transform_scales_before_rotating() -> None:
    placed = world_transform([Vector2D(1, 0)], POSITION, HEADING, SIDE, scale=Vector2D(3, 1))
    assert placed[0].is_close(Vector2D(10, 13))
