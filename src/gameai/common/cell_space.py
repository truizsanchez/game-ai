"""Cell-space partitioning (C++ ``Common/misc/CellSpacePartition.h``).

The world is divided into a grid of cells; each entity is stored in the cell containing its
position. A neighborhood query then only inspects the cells that overlap the query circle's
bounding box instead of every entity in the world.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from gameai.common.vector2d import Vector2D


class Positioned(Protocol):
    @property
    def position(self) -> Vector2D: ...

    def __hash__(self) -> int: ...


class CellSpacePartition[E: Positioned]:
    def __init__(self, width: float, height: float, cells_x: int, cells_y: int) -> None:
        self.width, self.height = width, height
        self.cells_x, self.cells_y = cells_x, cells_y
        self.cell_width, self.cell_height = width / cells_x, height / cells_y
        self.cells: list[list[E]] = [[] for _ in range(cells_x * cells_y)]
        self._cell_of: dict[E, int] = {}  # where each entity is currently stored

    def _cell_coords(self, pos: Vector2D) -> tuple[int, int]:
        x = min(max(int(pos.x / self.cell_width), 0), self.cells_x - 1)
        y = min(max(int(pos.y / self.cell_height), 0), self.cells_y - 1)
        return x, y

    def index_of(self, pos: Vector2D) -> int:
        x, y = self._cell_coords(pos)
        return y * self.cells_x + x

    def add(self, entity: E) -> None:
        index = self.index_of(entity.position)
        self.cells[index].append(entity)
        self._cell_of[entity] = index

    def update(self, entity: E) -> None:
        """Move ``entity`` to the cell of its current position, if it changed cell."""
        old, new = self._cell_of[entity], self.index_of(entity.position)
        if old != new:
            self.cells[old].remove(entity)
            self.cells[new].append(entity)
            self._cell_of[entity] = new

    def remove(self, entity: E) -> None:
        self.cells[self._cell_of.pop(entity)].remove(entity)

    def clear(self) -> None:
        for cell in self.cells:
            cell.clear()
        self._cell_of.clear()

    def cells_near(self, pos: Vector2D, radius: float) -> Iterator[list[E]]:
        """The cells overlapping the square of side ``2*radius`` centered on ``pos``."""
        x0, y0 = self._cell_coords(pos - Vector2D(radius, radius))
        x1, y1 = self._cell_coords(pos + Vector2D(radius, radius))
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                yield self.cells[y * self.cells_x + x]

    def neighbors(self, pos: Vector2D, radius: float) -> list[E]:
        """Entities strictly closer than ``radius`` to ``pos``."""
        radius_sq = radius * radius
        return [
            entity
            for cell in self.cells_near(pos, radius)
            for entity in cell
            if entity.position.distance_sq(pos) < radius_sq
        ]
