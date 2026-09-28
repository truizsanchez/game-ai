"""The steering sandbox (C++ ``GameWorld``): vehicles, obstacles, walls, a path, a crosshair."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

from gameai.ch03_steering.params import Params, load
from gameai.ch03_steering.vehicle import Vehicle
from gameai.common.cell_space import CellSpacePartition
from gameai.common.entity import BaseGameEntity, enforce_non_penetration
from gameai.common.geometry import Wall2D, circles_overlap, point_in_circle, walls_from_polygon
from gameai.common.steering import Path
from gameai.common.utils import random_clamped
from gameai.common.vector2d import Vector2D


@dataclass(eq=False)
class GameWorld:
    width: float
    height: float
    params: Params = field(default_factory=load)
    rng: random.Random = field(default_factory=random.Random)
    vehicles: list[Vehicle] = field(default_factory=list, init=False)
    obstacles: list[BaseGameEntity] = field(default_factory=list, init=False)
    walls: list[Wall2D] = field(default_factory=list, init=False)
    path: Path | None = field(default=None, init=False)
    crosshair: Vector2D = field(init=False)
    space_partitioning: bool = True
    non_penetration: bool = False

    def __post_init__(self) -> None:
        self.crosshair = Vector2D(self.width / 2, self.height / 2)
        p = self.params
        self.cell_space: CellSpacePartition[Vehicle] = CellSpacePartition(
            self.width, self.height, p.num_cells_x, p.num_cells_y
        )

    # --- population ---------------------------------------------------------------------
    def add_vehicle(self, position: Vector2D | None = None, **overrides: Any) -> Vehicle:
        """A vehicle with the default parameters (override any field by keyword)."""
        p, rng = self.params, self.rng
        if position is None:
            position = Vector2D(
                self.width / 2 + random_clamped(rng) * self.width / 2,
                self.height / 2 + random_clamped(rng) * self.height / 2,
            )
        settings: dict[str, Any] = {
            "bounding_radius": p.vehicle_scale,
            "heading": Vector2D.from_angle(rng.random() * math.tau),
            "mass": p.vehicle_mass,
            "max_speed": p.max_speed,
            "max_force": p.max_steering_force,
            "max_turn_rate": p.max_turn_rate_per_second,
        } | overrides
        vehicle = Vehicle(position=position, world=self, **settings)
        self.vehicles.append(vehicle)
        self.cell_space.add(vehicle)
        return vehicle

    def create_obstacles(self, count: int | None = None, min_gap: float = 20.0) -> None:
        """Random circular obstacles that don't overlap (``GameWorld::CreateObstacles``)."""
        p, rng, border = self.params, self.rng, 10
        self.obstacles.clear()
        for _ in range(p.num_obstacles if count is None else count):
            for _attempt in range(2000):
                radius = rng.randint(int(p.min_obstacle_radius), int(p.max_obstacle_radius))
                center = Vector2D(
                    rng.randint(radius + border, int(self.width) - radius - border),
                    rng.randint(radius + border, int(self.height) - radius - border),
                )
                if not any(
                    circles_overlap(center, radius + min_gap, o.position, o.bounding_radius)
                    for o in self.obstacles
                ):
                    self.obstacles.append(BaseGameEntity(center, radius))
                    break

    def create_walls(self, border: float = 20.0, corner: float = 0.2) -> None:
        """An octagonal arena, vertices anticlockwise so normals point inwards."""
        w, h = self.width, self.height
        dx, dy = (w - 2 * border) * corner, (h - 2 * border) * corner
        left, right, bottom, top = border, w - border, border, h - border
        self.walls = walls_from_polygon(
            [
                Vector2D(left + dx, bottom),
                Vector2D(right - dx, bottom),
                Vector2D(right, bottom + dy),
                Vector2D(right, top - dy),
                Vector2D(right - dx, top),
                Vector2D(left + dx, top),
                Vector2D(left, top - dy),
                Vector2D(left, bottom + dy),
            ]
        )

    def set_crosshair(self, position: Vector2D) -> None:
        """Move the target, unless the new spot is inside an obstacle."""
        if not any(
            point_in_circle(o.position, o.bounding_radius, position) for o in self.obstacles
        ):
            self.crosshair = position

    # --- queries and update ---------------------------------------------------------------
    def neighbors(self, position: Vector2D, radius: float) -> list[Vehicle]:
        """Vehicles closer than ``radius`` to ``position``."""
        if self.space_partitioning:
            return self.cell_space.neighbors(position, radius)
        radius_sq = radius * radius
        return [v for v in self.vehicles if v.position.distance_sq(position) < radius_sq]

    def update(self, dt: float) -> None:
        for vehicle in self.vehicles:
            vehicle.update(dt)
        if self.non_penetration:
            for vehicle in self.vehicles:
                reach = vehicle.bounding_radius * 4
                enforce_non_penetration(vehicle, self.neighbors(vehicle.position, reach))
                self.cell_space.update(vehicle)
