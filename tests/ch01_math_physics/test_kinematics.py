import math

import pytest

from gameai.ch01_math_physics.kinematics import (
    Body,
    angle_to_face,
    displacement,
    final_velocity,
    is_ahead,
    velocity_after_distance,
)
from gameai.common.vector2d import Vector2D


def test_troll_turns_to_face_the_princess() -> None:
    """The book gets 0.902 rad because it rounds N_TP to (0.62, 0.78) first."""
    theta = angle_to_face(Vector2D(0, 0), Vector2D(1, 0), Vector2D(4, 5))
    assert theta == pytest.approx(math.acos(4 / math.sqrt(41)))
    assert theta == pytest.approx(0.896, abs=1e-3)
    assert math.acos(0.62) == pytest.approx(0.902, abs=1e-3)


def test_dot_product_tells_ahead_from_behind() -> None:
    troll, north = Vector2D(0, 0), Vector2D(0, 1)
    assert is_ahead(troll, north, Vector2D(-5, 1))
    assert not is_ahead(troll, north, Vector2D(5, -1))


def test_constant_acceleration_equations() -> None:
    assert final_velocity(u=3, a=2, t=3) == 9  # eq. 1.82
    assert displacement(u=2, a=2, t=2) == 8  # eq. 1.88: from t=1 to t=3, starting at rest
    assert velocity_after_distance(u=0, a=9.8, dx=381) == pytest.approx(86.41, abs=0.01)  # 1.92


def test_force_gives_acceleration() -> None:
    """F = ma: the 2000 kg yacht accelerating at 1.5 m/s² needs 3000 N."""
    yacht = Body(mass=2000)
    yacht.update(1.0, Vector2D(3000, 0))
    assert yacht.acceleration == Vector2D(1.5, 0)


def test_table_1_1_car_accelerating_from_rest() -> None:
    car = Body(mass=1)
    velocities = []
    for _ in range(5):
        car.update(1.0, Vector2D(2, 0))
        velocities.append(car.velocity.x)
    assert velocities == [2, 4, 6, 8, 10]


def test_constant_velocity_without_force() -> None:
    vehicle = Body(mass=1, position=Vector2D(0, 0), velocity=Vector2D(3, 4))
    vehicle.update(0.5)
    assert vehicle.position == Vector2D(1.5, 2)
    assert vehicle.velocity == Vector2D(3, 4)
