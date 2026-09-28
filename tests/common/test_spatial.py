import random
from dataclasses import dataclass

import pytest

from gameai.common.cell_space import CellSpacePartition
from gameai.common.entity import BaseGameEntity, enforce_non_penetration
from gameai.common.geometry import (
    circles_overlap,
    point_in_circle,
    segment_intersection,
    walls_from_polygon,
)
from gameai.common.smoother import Smoother
from gameai.common.vector2d import Vector2D


@dataclass(eq=False)
class Dot:
    position: Vector2D


def test_cell_space_neighbors_match_brute_force() -> None:
    rng = random.Random(0)
    dots = [Dot(Vector2D(rng.uniform(0, 500), rng.uniform(0, 400))) for _ in range(300)]
    space: CellSpacePartition[Dot] = CellSpacePartition(500, 400, 7, 7)
    for dot in dots:
        space.add(dot)
    for query in dots[:20]:
        expected = {d for d in dots if d.position.distance_sq(query.position) < 60**2}
        assert set(space.neighbors(query.position, 60)) == expected


def test_cell_space_tracks_moving_entities() -> None:
    space: CellSpacePartition[Dot] = CellSpacePartition(100, 100, 4, 4)
    dot = Dot(Vector2D(10, 10))
    space.add(dot)
    dot.position = Vector2D(90, 90)
    space.update(dot)
    assert space.neighbors(Vector2D(90, 90), 5) == [dot]
    assert space.neighbors(Vector2D(10, 10), 5) == []
    space.remove(dot)
    assert space.neighbors(Vector2D(90, 90), 5) == []


def test_smoother_averages_recent_samples() -> None:
    smoother = Smoother(4, 0.0)
    assert [smoother.update(v) for v in (4.0, 4.0, 4.0, 4.0, 8.0)] == [1, 2, 3, 4, 5]
    vectors = Smoother(2, Vector2D())
    vectors.update(Vector2D(2, 0))
    assert vectors.update(Vector2D(0, 2)) == Vector2D(1, 1)


def test_segment_intersection() -> None:
    hit = segment_intersection(Vector2D(0, 0), Vector2D(10, 0), Vector2D(4, -1), Vector2D(4, 1))
    assert hit is not None
    assert hit.distance == pytest.approx(4)
    assert hit.point.is_close(Vector2D(4, 0))
    parallel = segment_intersection(Vector2D(0, 0), Vector2D(1, 0), Vector2D(0, 1), Vector2D(1, 1))
    assert parallel is None
    short = segment_intersection(Vector2D(0, 0), Vector2D(3, 0), Vector2D(4, -1), Vector2D(4, 1))
    assert short is None


def test_anticlockwise_polygon_walls_face_inwards() -> None:
    square = [Vector2D(0, 0), Vector2D(10, 0), Vector2D(10, 10), Vector2D(0, 10)]
    center = Vector2D(5, 5)
    for wall in walls_from_polygon(square):
        assert wall.normal.dot(center - wall.center) > 0


def test_circle_tests() -> None:
    assert circles_overlap(Vector2D(0, 0), 2, Vector2D(3, 0), 2)
    assert not circles_overlap(Vector2D(0, 0), 1, Vector2D(3, 0), 1)
    assert point_in_circle(Vector2D(0, 0), 2, Vector2D(1, 1))


def test_enforce_non_penetration() -> None:
    a, b = BaseGameEntity(Vector2D(0, 0), 2), BaseGameEntity(Vector2D(3, 0), 2)
    enforce_non_penetration(a, [a, b])
    assert a.position.distance(b.position) == pytest.approx(4)
