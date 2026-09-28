"""Interactive demos for chapter 1. Run with ``python -m gameai.ch01_math_physics``."""

from __future__ import annotations

import math
import random

import arcade

from gameai.ch01_math_physics.kinematics import Body, angle_to_face, is_ahead
from gameai.common.transformations import point_to_local_space, world_transform
from gameai.common.vector2d import Vector2D, is_in_fov, wrap_around
from gameai.common.view import (
    HEIGHT,
    WIDTH,
    Demo,
    draw_arrow,
    draw_circle,
    draw_line,
    draw_polygon,
)

CENTER = Vector2D(WIDTH / 2, HEIGHT / 2)
TURN_RATE = math.pi  # radians per second
DART = [Vector2D(15, 0), Vector2D(-10, 8), Vector2D(-10, -8)]  # local space, like the ch.3 vehicle


class TrollAndPrincess(Demo):
    """The dot product at work (section "A Practical Example of Vector Mathematics")."""

    title = "1. Eric the Troll: dot product"
    help = (
        "Mouse: move the princess",
        "Left/Right: turn the troll",
        "F: toggle 90° field of view",
    )

    def __init__(self) -> None:
        super().__init__()
        self.heading = Vector2D(1, 0)
        self.princess = Vector2D(CENTER.x + 150, CENTER.y + 180)
        self.show_fov = False

    def step(self, dt: float) -> None:
        turn = (arcade.key.LEFT in self.held) - (arcade.key.RIGHT in self.held)
        self.heading = self.heading.rotate(turn * TURN_RATE * dt)

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int) -> None:
        self.princess = Vector2D(x, y)

    def on_key_press(self, symbol: int, modifiers: int) -> bool | None:
        if symbol == arcade.key.F:
            self.show_fov = not self.show_fov
            return True
        return super().on_key_press(symbol, modifiers)

    def draw(self) -> None:
        troll, heading, princess = CENTER, self.heading, self.princess
        side = heading.perp()
        # Facing plane: everything on the heading's side of this line is "ahead".
        draw_line(troll - side * 1000, troll + side * 1000, arcade.color.DIM_GRAY)
        if self.show_fov:
            for half in (math.pi / 4, -math.pi / 4):
                draw_arrow(troll, troll + heading.rotate(half) * 300, arcade.color.DARK_YELLOW, 1)

        ahead = is_ahead(troll, heading, princess)
        draw_arrow(troll, princess, arcade.color.GREEN if ahead else arcade.color.RED)
        draw_arrow(troll, troll + heading * 80, arcade.color.WHITE, 3)
        draw_circle(troll, 14, arcade.color.OLIVE)
        draw_circle(princess, 8, arcade.color.PINK)

        theta = angle_to_face(troll, heading, princess)
        turn = heading.sign(princess - troll).name.lower()
        fov = is_in_fov(troll, heading, princess, math.pi / 2)
        self.status = (
            f"θ = {theta:.3f} rad ({math.degrees(theta):.1f}°), turn {turn}  |  "
            f"{'ahead' if ahead else 'behind'}  |  {'in' if fov else 'out of'} FOV"
        )


class LocalSpace(Demo):
    """Figures 1.23-1.25: the same obstacles seen in world space and in the vehicle's space."""

    title = "2. World space vs local space"
    help = ("Tab: toggle world / local view",)

    def __init__(self) -> None:
        super().__init__()
        rng = random.Random(1)
        self.obstacles = [
            (
                Vector2D(rng.uniform(50, WIDTH - 50), rng.uniform(50, HEIGHT - 50)),
                rng.uniform(8, 25),
            )
            for _ in range(12)
        ]
        self.angle = 0.0
        self.local_view = False

    @property
    def position(self) -> Vector2D:
        return CENTER + Vector2D.from_angle(self.angle, 200)

    @property
    def heading(self) -> Vector2D:
        return Vector2D.from_angle(self.angle + math.pi / 2)  # tangent to the circle

    def step(self, dt: float) -> None:
        self.angle += 0.4 * dt

    def on_key_press(self, symbol: int, modifiers: int) -> bool | None:
        if symbol == arcade.key.TAB:
            self.local_view = not self.local_view
            return True
        return super().on_key_press(symbol, modifiers)

    def draw(self) -> None:
        heading, pos = self.heading, self.position
        side = heading.perp()
        centers = [center for center, _ in self.obstacles]
        if self.local_view:
            # Local space drawn with its origin at the screen center, heading pointing right.
            centers = [CENTER + point_to_local_space(c, heading, side, pos) for c in centers]
            draw_arrow(CENTER, CENTER + Vector2D(60, 0), arcade.color.RED)
            draw_arrow(CENTER, CENTER + Vector2D(0, 60), arcade.color.GREEN)
            draw_polygon([CENTER + p for p in DART], arcade.color.WHITE)
        else:
            draw_circle(CENTER, 200, arcade.color.DIM_GRAY, filled=False)
            draw_arrow(pos, pos + heading * 60, arcade.color.RED)
            draw_arrow(pos, pos + side * 60, arcade.color.GREEN)
            draw_polygon(world_transform(DART, pos, heading, side), arcade.color.WHITE)
        for center, (_, radius) in zip(centers, self.obstacles, strict=True):
            draw_circle(center, radius, arcade.color.LIGHT_BLUE, filled=False, width=2)

        nearest = min(self.obstacles, key=lambda o: o[0].distance_sq(pos))[0]
        local = point_to_local_space(nearest, heading, side, pos)
        self.status = (
            f"{'LOCAL' if self.local_view else 'WORLD'} view  |  nearest obstacle in local "
            f"space: ({local.x:.0f}, {local.y:.0f})  (red = heading/x, green = side/y)"
        )


class SpaceShip(Demo):
    """Force → acceleration → velocity → position (section "Force")."""

    title = "3. Spaceship: F = ma"
    help = (
        "Up: thrust  Left/Right: turn",
        "+/-: change mass",
        "blue = velocity, red = acceleration",
    )
    THRUST = 20_000.0  # newtons (one pixel = one meter)

    def __init__(self) -> None:
        super().__init__()
        self.ship = Body(mass=500.0, position=CENTER)
        self.heading = Vector2D(0, 1)

    def step(self, dt: float) -> None:
        turn = (arcade.key.LEFT in self.held) - (arcade.key.RIGHT in self.held)
        self.heading = self.heading.rotate(turn * TURN_RATE * dt)
        force = self.heading * self.THRUST if arcade.key.UP in self.held else Vector2D()
        self.ship.update(dt, force)
        self.ship.position = wrap_around(self.ship.position, WIDTH, HEIGHT)
        ship = self.ship
        self.status = (
            f"mass {ship.mass:.0f} kg  |  a = {ship.acceleration.length():.1f} m/s²  |  "
            f"speed {ship.velocity.length():.1f} m/s"
        )

    def on_key_press(self, symbol: int, modifiers: int) -> bool | None:
        match symbol:
            case arcade.key.PLUS | arcade.key.EQUAL | arcade.key.NUM_ADD:
                self.ship.mass *= 1.5
            case arcade.key.MINUS | arcade.key.NUM_SUBTRACT:
                self.ship.mass /= 1.5
            case _:
                return super().on_key_press(symbol, modifiers)
        return True

    def draw(self) -> None:
        ship, heading = self.ship, self.heading
        hull = world_transform(DART, ship.position, heading, heading.perp(), Vector2D(1.5, 1.5))
        draw_polygon(hull, arcade.color.LIGHT_GRAY)
        draw_arrow(ship.position, ship.position + ship.velocity, arcade.color.SKY_BLUE)
        draw_arrow(ship.position, ship.position + ship.acceleration, arcade.color.RED)


DEMOS = (TrollAndPrincess, LocalSpace, SpaceShip)
