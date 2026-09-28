"""2D affine transformation matrix (C++ ``Common/2D/C2DMatrix.h``).

Like the C++ class, it uses the *row vector* convention: a point is the row ``[x, y, 1]``
multiplied on the left of the matrix. Consequently ``a @ b`` means "apply ``a``, then ``b``",
which lets transforms be chained in reading order::

    rotate = Matrix2D.rotation_from(heading, side)
    to_world = Matrix2D.scaling(sx, sy) @ rotate @ Matrix2D.translation(x, y)

Instead of mutating one matrix with ``Rotate``/``Translate`` calls, each factory returns an
immutable matrix and ``@`` composes them.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

from gameai.common.vector2d import Vector2D


@dataclass(frozen=True, slots=True)
class Matrix2D:
    """The six meaningful entries of a 3x3 affine matrix; the third column is always (0, 0, 1)."""

    m11: float = 1.0
    m12: float = 0.0
    m21: float = 0.0
    m22: float = 1.0
    m31: float = 0.0  # translation x
    m32: float = 0.0  # translation y

    @classmethod
    def identity(cls) -> Matrix2D:
        return cls()

    @classmethod
    def translation(cls, x: float, y: float) -> Matrix2D:
        return cls(m31=x, m32=y)

    @classmethod
    def scaling(cls, sx: float, sy: float) -> Matrix2D:
        return cls(m11=sx, m22=sy)

    @classmethod
    def rotation(cls, radians: float) -> Matrix2D:
        """Anticlockwise rotation around the origin."""
        cos, sin = math.cos(radians), math.sin(radians)
        return cls(m11=cos, m12=sin, m21=-sin, m22=cos)

    @classmethod
    def rotation_from(cls, heading: Vector2D, side: Vector2D) -> Matrix2D:
        """Rotation that maps the x axis onto ``heading`` and the y axis onto ``side``."""
        return cls(m11=heading.x, m12=heading.y, m21=side.x, m22=side.y)

    def __matmul__(self, other: Matrix2D) -> Matrix2D:
        a, b = self, other
        return Matrix2D(
            m11=a.m11 * b.m11 + a.m12 * b.m21,
            m12=a.m11 * b.m12 + a.m12 * b.m22,
            m21=a.m21 * b.m11 + a.m22 * b.m21,
            m22=a.m21 * b.m12 + a.m22 * b.m22,
            m31=a.m31 * b.m11 + a.m32 * b.m21 + b.m31,
            m32=a.m31 * b.m12 + a.m32 * b.m22 + b.m32,
        )

    def transform(self, point: Vector2D) -> Vector2D:
        return Vector2D(
            self.m11 * point.x + self.m21 * point.y + self.m31,
            self.m12 * point.x + self.m22 * point.y + self.m32,
        )

    def transform_all(self, points: Iterable[Vector2D]) -> list[Vector2D]:
        return [self.transform(p) for p in points]
