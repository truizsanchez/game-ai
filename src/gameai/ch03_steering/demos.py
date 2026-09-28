"""Interactive steering demos. Run with ``python -m gameai.ch03_steering``."""

from __future__ import annotations

import random
import time
from typing import ClassVar

import arcade

from gameai.ch03_steering.behaviors_flag import Behavior, Summing
from gameai.ch03_steering.vehicle import Vehicle
from gameai.ch03_steering.world import GameWorld
from gameai.common.steering import (
    Deceleration,
    Path,
    detection_box_length,
    hiding_position,
)
from gameai.common.transformations import point_to_world_space, world_transform
from gameai.common.vector2d import Vector2D
from gameai.common.view import (
    HEIGHT,
    WIDTH,
    Color,
    Demo,
    VehicleSprites,
    draw_arrow,
    draw_circle,
    draw_line,
    draw_polyline,
)

BLUE, RED, GREEN, GRAY = (
    arcade.color.SKY_BLUE,
    arcade.color.RED,
    arcade.color.GREEN,
    arcade.color.GRAY,
)


class SteeringDemo(Demo):
    """Base for the chapter's demos: a world, vehicle drawing and common debug overlays."""

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        cls.help = (*cls.help, "F: show steering forces")

    def __init__(self) -> None:
        super().__init__()
        self.world = GameWorld(WIDTH, HEIGHT, rng=random.Random(7))
        self.sprites = VehicleSprites()
        self.colors: dict[Vehicle, Color] = {}
        self.show_force = False
        self.setup()

    def setup(self) -> None:
        """Populate ``self.world``."""

    def add(self, behaviors: Behavior, color: Color = BLUE, **overrides: object) -> Vehicle:
        vehicle = self.world.add_vehicle(**overrides)  # type: ignore[arg-type]
        vehicle.steering.active = behaviors
        self.colors[vehicle] = color
        return vehicle

    def step(self, dt: float) -> None:
        self.world.update(dt)

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> None:
        self.world.set_crosshair(Vector2D(x, y))

    def on_key_press(self, symbol: int, modifiers: int) -> bool | None:
        if symbol == arcade.key.F:
            self.show_force = not self.show_force
            return True
        return super().on_key_press(symbol, modifiers)

    def draw(self) -> None:
        world = self.world
        for obstacle in world.obstacles:
            draw_circle(obstacle.position, obstacle.bounding_radius, GRAY, filled=False, width=2)
        for wall in world.walls:
            draw_line(wall.start, wall.end, arcade.color.LIGHT_GRAY, 2)
            draw_line(wall.center, wall.center + wall.normal * 8, arcade.color.LIGHT_GRAY)
        self.draw_overlays()
        self.sprites.draw(
            [
                (v.position, v.display_heading, v.bounding_radius * 1.5, self.colors.get(v, BLUE))
                for v in world.vehicles
            ]
        )
        if self.show_force:
            for v in world.vehicles:
                draw_line(v.position, v.position + v.steering.force * 0.1, RED)

    def draw_overlays(self) -> None:
        """Extra debug drawing under the vehicles."""

    def draw_crosshair(self) -> None:
        c = self.world.crosshair
        draw_circle(c, 5, RED, filled=False)
        draw_line(c - Vector2D(9, 0), c + Vector2D(9, 0), RED)
        draw_line(c - Vector2D(0, 9), c + Vector2D(0, 9), RED)


class SeekFleeArrive(SteeringDemo):
    title = "1. Seek, flee and arrive"
    help = ("Click: move the target", "S/L/A: seek / flee / arrive", "D: arrive deceleration")
    MODES: ClassVar[dict[int, Behavior]] = {
        arcade.key.S: Behavior.SEEK,
        arcade.key.L: Behavior.FLEE,
        arcade.key.A: Behavior.ARRIVE,
    }

    def setup(self) -> None:
        self.vehicle = self.add(Behavior.SEEK, bounding_radius=8, position=Vector2D(100, 100))

    def on_key_press(self, symbol: int, modifiers: int) -> bool | None:
        steering = self.vehicle.steering
        if symbol in self.MODES:
            steering.active = self.MODES[symbol]
        elif symbol == arcade.key.D:
            order = list(Deceleration)
            steering.deceleration = order[(order.index(steering.deceleration) + 1) % len(order)]
        else:
            return super().on_key_press(symbol, modifiers)
        return True

    def draw_overlays(self) -> None:
        self.draw_crosshair()
        s = self.vehicle.steering
        mode = s.active.name or ""
        extra = f" ({s.deceleration.name.lower()})" if s.is_on(Behavior.ARRIVE) else ""
        self.status = f"{mode.lower()}{extra}  |  speed {self.vehicle.speed:.0f}"


class PursuitEvade(SteeringDemo):
    title = "2. Pursuit and evade"
    help = ("A wandering evader (blue) and a pursuer (red)", "Circle: predicted interception point")

    def setup(self) -> None:
        self.pursuer = self.add(Behavior.PURSUIT, RED, bounding_radius=8, max_speed=160)
        self.evader = self.add(
            Behavior.WANDER | Behavior.EVADE, BLUE, bounding_radius=8, max_speed=120
        )
        self.pursuer.steering.pursuit_target = self.evader
        self.evader.steering.evade_target = self.pursuer
        # params.toml gives evade a tiny weight (tuned for the flock fleeing the shark).
        self.evader.steering.weights[Behavior.EVADE] = self.world.params.weights[Behavior.SEEK]

    def draw_overlays(self) -> None:
        p, e = self.pursuer, self.evader
        look_ahead = p.position.distance(e.position) / (p.max_speed + e.speed)
        predicted = e.position + e.velocity * look_ahead
        draw_circle(predicted, 4, RED, filled=False)
        draw_line(p.position, predicted, (255, 0, 0, 90))
        self.status = f"distance {p.position.distance(e.position):.0f}"


class Wander(SteeringDemo):
    title = "3. Wander"
    help = ("J/K: jitter -/+  R/T: radius -/+  G/Y: distance -/+",)
    STEP: ClassVar[dict[int, tuple[str, float]]] = {
        arcade.key.J: ("jitter", -10),
        arcade.key.K: ("jitter", 10),
        arcade.key.R: ("radius", -0.2),
        arcade.key.T: ("radius", 0.2),
        arcade.key.G: ("distance", -0.5),
        arcade.key.Y: ("distance", 0.5),
    }

    def setup(self) -> None:
        self.leader = self.add(Behavior.WANDER, GREEN, bounding_radius=10, max_speed=100)
        for _ in range(15):
            self.add(Behavior.WANDER, max_speed=100)

    def on_key_press(self, symbol: int, modifiers: int) -> bool | None:
        if symbol not in self.STEP:
            return super().on_key_press(symbol, modifiers)
        name, delta = self.STEP[symbol]
        for v in self.world.vehicles:
            state = v.steering.wander_state
            setattr(state, name, max(0.0, getattr(state, name) + delta))
        return True

    def draw_overlays(self) -> None:
        v, state = self.leader, self.leader.steering.wander_state
        r = v.bounding_radius
        center = point_to_world_space(
            Vector2D(state.distance * r, 0), v.heading, v.side, v.position
        )
        target = point_to_world_space(
            (state.target + Vector2D(state.distance, 0)) * r, v.heading, v.side, v.position
        )
        draw_circle(center, state.radius * r, GREEN, filled=False)
        draw_circle(target, 3, RED)
        self.status = (
            f"jitter {state.jitter:.0f}/s  radius {state.radius:.1f}  distance {state.distance:.1f}"
            "  (in agent radii)"
        )


class ObstacleAvoidance(SteeringDemo):
    title = "4. Obstacle avoidance"
    help = ("Detection box of the green vehicle; red when an obstacle is inside",)

    def setup(self) -> None:
        self.world.create_obstacles()
        behaviors = Behavior.WANDER | Behavior.OBSTACLE_AVOIDANCE
        self.first = self.add(behaviors, GREEN, bounding_radius=8, max_speed=100)
        for _ in range(12):
            self.add(behaviors, bounding_radius=6, max_speed=100)

    def draw_overlays(self) -> None:
        v = self.first
        length = detection_box_length(v, self.world.params.min_detection_box_length)
        r = v.bounding_radius
        box = [Vector2D(0, r), Vector2D(length, r), Vector2D(length, -r), Vector2D(0, -r)]
        box = world_transform(box, v.position, v.heading, v.side)
        hit = bool(v.steering.force_for(Behavior.OBSTACLE_AVOIDANCE))
        draw_polyline(box, RED if hit else GRAY, closed=True)


class WallAvoidance(SteeringDemo):
    title = "5. Wall avoidance"
    help = ("Feelers of the green vehicle are drawn in orange",)

    def setup(self) -> None:
        self.world.create_walls()
        behaviors = Behavior.WANDER | Behavior.WALL_AVOIDANCE
        self.first = self.add(behaviors, GREEN, bounding_radius=8, max_speed=100)
        for _ in range(12):
            self.add(behaviors, bounding_radius=6, max_speed=100)
        for v in self.world.vehicles:  # start everyone inside the arena
            v.position = Vector2D(
                self.world.rng.uniform(200, 600), self.world.rng.uniform(150, 450)
            )

    def draw_overlays(self) -> None:
        for feeler in self.first.steering.feelers:
            draw_line(self.first.position, feeler, arcade.color.ORANGE)


class InterposeHide(SteeringDemo):
    title = "6. Interpose and hide"
    help = ("Red interposes between the two blue wanderers", "Green ones hide from the left blue")

    def setup(self) -> None:
        self.world.create_obstacles()
        self.a = self.add(Behavior.WANDER, BLUE, bounding_radius=8, max_speed=80)
        self.b = self.add(Behavior.WANDER, BLUE, bounding_radius=8, max_speed=80)
        interposer = self.add(Behavior.INTERPOSE, RED, bounding_radius=8, max_speed=200)
        interposer.steering.interpose_targets = (self.a, self.b)
        for _ in range(3):
            hider = self.add(Behavior.HIDE | Behavior.OBSTACLE_AVOIDANCE, GREEN, bounding_radius=6)
            hider.steering.hide_target = self.a

    def draw_overlays(self) -> None:
        draw_line(self.a.position, self.b.position, (120, 120, 120, 120))
        for obstacle in self.world.obstacles:
            draw_circle(hiding_position(obstacle, self.a.position), 3, GREEN, filled=False)


class PathAndFormation(SteeringDemo):
    title = "7. Path following and offset pursuit"
    help = ("U: new random path", "Followers keep a V formation behind the leader")
    OFFSETS = (Vector2D(-20, 20), Vector2D(-20, -20), Vector2D(-40, 40), Vector2D(-40, -40))

    def setup(self) -> None:
        self.leader = self.add(Behavior.FOLLOW_PATH, RED, bounding_radius=8, max_speed=90)
        self.new_path()
        for offset in self.OFFSETS:
            follower = self.add(Behavior.OFFSET_PURSUIT, BLUE, bounding_radius=6)
            follower.steering.leader, follower.steering.offset = self.leader, offset

    def new_path(self) -> None:
        rng = self.world.rng
        path = Path.random(rng.randint(3, 7), Vector2D(60, 60), Vector2D(WIDTH - 60, HEIGHT - 60),
                           rng=rng)  # fmt: skip
        self.world.path = self.leader.steering.path = path

    def on_key_press(self, symbol: int, modifiers: int) -> bool | None:
        if symbol == arcade.key.U:
            self.new_path()
            return True
        return super().on_key_press(symbol, modifiers)

    def draw_overlays(self) -> None:
        if path := self.world.path:
            draw_polyline(path.waypoints, arcade.color.ORANGE, closed=path.looped)
            draw_circle(path.current, 5, arcade.color.ORANGE, filled=False)


class Flocking(SteeringDemo):
    title = "8. Flocking"
    help = (
        "Space: toggle cell-space partitioning  M: summing method",
        "O: show green's neighbors  I: smoothing  Z: zero overlap",
    )
    AGENTS = 200

    def setup(self) -> None:
        world = self.world
        self.shark = self.add(Behavior.WANDER, RED, bounding_radius=10, max_speed=70)
        for i in range(self.AGENTS):
            v = self.add(Behavior.FLOCKING | Behavior.EVADE, GREEN if i == 0 else BLUE)
            v.steering.evade_target = self.shark
        self.first = world.vehicles[1]
        self.show_neighbors = False
        self.update_ms = 0.0

    def step(self, dt: float) -> None:
        start = time.perf_counter()
        super().step(dt)
        self.update_ms = 0.9 * self.update_ms + 0.1 * (time.perf_counter() - start) * 1000

    def on_key_press(self, symbol: int, modifiers: int) -> bool | None:
        world = self.world
        match symbol:
            case arcade.key.SPACE:
                world.space_partitioning = not world.space_partitioning
            case arcade.key.M:
                order = list(Summing)
                for v in world.vehicles:
                    v.steering.summing = order[(order.index(v.steering.summing) + 1) % len(order)]
            case arcade.key.O:
                self.show_neighbors = not self.show_neighbors
            case arcade.key.I:
                for v in world.vehicles:
                    v.smoothing = not v.smoothing
            case arcade.key.Z:
                world.non_penetration = not world.non_penetration
            case _:
                return super().on_key_press(symbol, modifiers)
        return True

    def draw_overlays(self) -> None:
        world, first = self.world, self.first
        if self.show_neighbors:
            radius = world.params.view_distance
            draw_circle(first.position, radius, GREEN, filled=False)
            for n in first.steering.neighbors:
                draw_circle(n.position, 5, arcade.color.YELLOW, filled=False)
            if world.space_partitioning:
                cs = world.cell_space
                for i in range(1, cs.cells_x):
                    x = i * cs.cell_width
                    draw_line(Vector2D(x, 0), Vector2D(x, HEIGHT), (80, 80, 80, 255))
                for j in range(1, cs.cells_y):
                    y = j * cs.cell_height
                    draw_line(Vector2D(0, y), Vector2D(WIDTH, y), (80, 80, 80, 255))
        draw_arrow(self.shark.position, self.shark.position + self.shark.heading * 25, RED, 1)
        summing = first.steering.summing.name.lower().replace("_", " ")
        partitioning = "on" if world.space_partitioning else "off"
        self.status = (
            f"{len(world.vehicles)} agents  |  partitioning {partitioning}"
            f"  |  {summing}  |  smoothing {'on' if first.smoothing else 'off'}"
            f"  |  update {self.update_ms:.1f} ms"
        )


DEMOS = (
    SeekFleeArrive,
    PursuitEvade,
    Wander,
    ObstacleAvoidance,
    WallAvoidance,
    InterposeHide,
    PathAndFormation,
    Flocking,
)
