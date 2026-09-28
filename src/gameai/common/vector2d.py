"""2D vector (C++ ``Common/2D/Vector2D.h``).

Unlike the C++ struct, :class:`Vector2D` is immutable: every operation returns a new vector,
so ``v.normalize()`` replaces the in-place ``v.Normalize()`` and ``Vec2DNormalize(v)``.

Coordinates follow arcade's convention (y axis pointing *up*), whereas the book's examples
use a Windows GDI window (y axis pointing *down*). This only matters for :meth:`Vector2D.sign`
and for the direction :meth:`Vector2D.perp` rotates, both documented below.
"""

from __future__ import annotations

import math
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from enum import IntEnum

EPSILON = sys.float_info.epsilon


class Rotation(IntEnum):
    """Result of :meth:`Vector2D.sign`."""

    CLOCKWISE = 1
    ANTICLOCKWISE = -1


@dataclass(frozen=True, slots=True)
class Vector2D:
    x: float = 0.0
    y: float = 0.0

    @classmethod
    def from_angle(cls, radians: float, length: float = 1.0) -> Vector2D:
        """Vector of the given length pointing ``radians`` anticlockwise from the x axis."""
        return cls(length * math.cos(radians), length * math.sin(radians))

    # --- arithmetic ---------------------------------------------------------
    def __add__(self, other: Vector2D) -> Vector2D:
        return Vector2D(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Vector2D) -> Vector2D:
        return Vector2D(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> Vector2D:
        return Vector2D(self.x * scalar, self.y * scalar)

    __rmul__ = __mul__

    def __truediv__(self, scalar: float) -> Vector2D:
        return Vector2D(self.x / scalar, self.y / scalar)

    def __neg__(self) -> Vector2D:
        """The reverse vector (``GetReverse`` in C++)."""
        return Vector2D(-self.x, -self.y)

    def __iter__(self) -> Iterator[float]:
        """Allows ``x, y = v`` and passing ``(*v,)`` wherever arcade expects a point."""
        yield self.x
        yield self.y

    def __bool__(self) -> bool:
        """False for the zero vector (``isZero`` in C++)."""
        return self.length_sq() >= sys.float_info.min

    def is_close(self, other: Vector2D, abs_tol: float = 1e-12) -> bool:
        """Tolerant equality; ``==`` is exact, as usual for floats in Python."""
        return math.isclose(self.x, other.x, abs_tol=abs_tol) and math.isclose(
            self.y, other.y, abs_tol=abs_tol
        )

    # --- magnitude ----------------------------------------------------------
    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def length_sq(self) -> float:
        """Squared length, avoiding the square root when only comparing lengths."""
        return self.x * self.x + self.y * self.y

    def normalize(self) -> Vector2D:
        """Unit vector with the same direction. The zero vector stays zero."""
        length = self.length()
        return self / length if length > EPSILON else self

    def truncate(self, max_length: float) -> Vector2D:
        """This vector, shortened if needed so its length does not exceed ``max_length``."""
        return self.normalize() * max_length if self.length() > max_length else self

    # --- products and relations ---------------------------------------------
    def dot(self, other: Vector2D) -> float:
        return self.x * other.x + self.y * other.y

    def cross(self, other: Vector2D) -> float:
        """z component of the 3D cross product: positive if ``other`` is anticlockwise."""
        return self.x * other.y - self.y * other.x

    def sign(self, other: Vector2D) -> Rotation:
        """Whether ``other`` is clockwise or anticlockwise of this vector (y axis up)."""
        return Rotation.ANTICLOCKWISE if self.cross(other) > 0 else Rotation.CLOCKWISE

    def perp(self) -> Vector2D:
        """This vector rotated 90 degrees anticlockwise (y axis up).

        Same formula as the C++ ``Perp``; with the book's y-down axis it looks clockwise.
        An agent's side vector is ``heading.perp()``, so it points to the agent's left.
        """
        return Vector2D(-self.y, self.x)

    def distance(self, other: Vector2D) -> float:
        return math.hypot(other.x - self.x, other.y - self.y)

    def distance_sq(self, other: Vector2D) -> float:
        dx, dy = other.x - self.x, other.y - self.y
        return dx * dx + dy * dy

    def reflect(self, normal: Vector2D) -> Vector2D:
        """This vector bounced off a surface with the given unit ``normal``."""
        return self - 2.0 * self.dot(normal) * normal

    def angle_to(self, other: Vector2D) -> float:
        """Unsigned angle in radians between the two vectors (dot product, eq. 1.69)."""
        lengths = self.length() * other.length()
        if lengths <= EPSILON:
            return 0.0
        return math.acos(max(-1.0, min(1.0, self.dot(other) / lengths)))

    def rotate(self, radians: float) -> Vector2D:
        """This vector rotated anticlockwise around the origin."""
        cos, sin = math.cos(radians), math.sin(radians)
        return Vector2D(self.x * cos - self.y * sin, self.x * sin + self.y * cos)


ZERO = Vector2D()
UNIT_X = Vector2D(1.0, 0.0)


def wrap_around(pos: Vector2D, max_x: float, max_y: float) -> Vector2D:
    """Treat the world as a toroid: leaving one edge re-enters from the opposite one."""
    x, y = pos
    if x > max_x:
        x = 0.0
    elif x < 0:
        x = max_x
    if y > max_y:
        y = 0.0
    elif y < 0:
        y = max_y
    return Vector2D(x, y)


def is_in_fov(position: Vector2D, facing: Vector2D, target: Vector2D, fov: float) -> bool:
    """True if ``target`` is inside the field of view (radians) of an entity at ``position``.

    ``facing`` must be normalized. C++: ``isSecondInFOVOfFirst``.
    """
    return facing.dot((target - position).normalize()) >= math.cos(fov / 2.0)
