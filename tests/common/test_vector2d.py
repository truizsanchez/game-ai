import math

import pytest

from gameai.common.vector2d import ZERO, Rotation, Vector2D, is_in_fov, wrap_around


def test_adding_camerons_vectors() -> None:
    """Eq. 1.57: following the four vectors is the same as following their sum."""
    route = [Vector2D(-5, 5), Vector2D(0, -10), Vector2D(13, 7), Vector2D(-4, 3)]
    assert sum(route, ZERO) == Vector2D(4, 5)


def test_arithmetic() -> None:
    v = Vector2D(4, 5)
    assert v * 2 == 2 * v == Vector2D(8, 10)
    assert v / 2 == Vector2D(2, 2.5)
    assert v - v == ZERO
    assert -v == Vector2D(-4, -5)
    assert tuple(v) == (4, 5)


def test_length_and_normalize() -> None:
    """Eqs. 1.58 and 1.62."""
    v = Vector2D(4, 5)
    assert v.length() == pytest.approx(math.sqrt(41))
    assert v.length_sq() == 41
    n = v.normalize()
    assert (round(n.x, 2), round(n.y, 2)) == (0.62, 0.78)
    assert n.length() == pytest.approx(1)
    assert ZERO.normalize() == ZERO


def test_zero_is_falsy() -> None:
    assert not ZERO
    assert Vector2D(0, 1e-3)


def test_truncate() -> None:
    assert Vector2D(30, 40).truncate(5).is_close(Vector2D(3, 4))
    assert Vector2D(3, 4).truncate(10) == Vector2D(3, 4)


def test_dot_and_angle() -> None:
    assert Vector2D(1, 0).dot(Vector2D(0, 1)) == 0
    assert Vector2D(1, 0).angle_to(Vector2D(0, 3)) == pytest.approx(math.pi / 2)
    assert Vector2D(1, 0).angle_to(Vector2D(-2, 0)) == pytest.approx(math.pi)


def test_perp_is_anticlockwise_with_y_up() -> None:
    assert Vector2D(1, 0).perp() == Vector2D(0, 1)


def test_sign() -> None:
    heading = Vector2D(1, 0)
    assert heading.sign(Vector2D(1, 1)) is Rotation.ANTICLOCKWISE
    assert heading.sign(Vector2D(1, -1)) is Rotation.CLOCKWISE


def test_reflect_bounces_off_a_wall() -> None:
    ball = Vector2D(3, -4)
    floor_normal = Vector2D(0, 1)
    assert ball.reflect(floor_normal) == Vector2D(3, 4)


def test_rotate_and_from_angle() -> None:
    assert Vector2D(1, 0).rotate(math.pi / 2).is_close(Vector2D(0, 1))
    assert Vector2D.from_angle(math.pi, 2).is_close(Vector2D(-2, 0))


def test_distance() -> None:
    assert Vector2D(1, 1).distance(Vector2D(4, 5)) == 5
    assert Vector2D(1, 1).distance_sq(Vector2D(4, 5)) == 25


@pytest.mark.parametrize(
    ("pos", "expected"),
    [
        (Vector2D(101, 50), Vector2D(0, 50)),
        (Vector2D(-1, 50), Vector2D(100, 50)),
        (Vector2D(50, 201), Vector2D(50, 0)),
        (Vector2D(50, -1), Vector2D(50, 200)),
        (Vector2D(50, 50), Vector2D(50, 50)),
    ],
)
def test_wrap_around(pos: Vector2D, expected: Vector2D) -> None:
    assert wrap_around(pos, 100, 200) == expected


def test_is_in_fov() -> None:
    here, facing = Vector2D(0, 0), Vector2D(1, 0)
    assert is_in_fov(here, facing, Vector2D(10, 3), math.pi / 2)
    assert not is_in_fov(here, facing, Vector2D(3, 10), math.pi / 2)
    assert not is_in_fov(here, facing, Vector2D(-10, 0), math.pi / 2)
