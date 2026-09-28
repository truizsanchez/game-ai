"""Minimal arcade harness shared by every chapter's demos.

Each demo is an :class:`arcade.View` subclass of :class:`Demo`. The simulation advances in
:meth:`Demo.step` at a fixed rate (arcade's ``on_fixed_update``), independent of the frame
rate, as the book recommends in chapter 1. Common keys:

- ``P`` pause / resume, ``N`` advance one step while paused
- ``H`` show / hide the help overlay
- ``1``-``9`` switch between the demos passed to :func:`run`
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from typing import ClassVar

import arcade
from PIL import Image, ImageDraw

from gameai.common.vector2d import Vector2D

type Color = tuple[int, int, int] | tuple[int, int, int, int]

WIDTH, HEIGHT = 800, 600
FIXED_RATE = 1 / 60


class Demo(arcade.View):
    title: ClassVar[str] = "Demo"
    help: ClassVar[Sequence[str]] = ()

    def __init__(self) -> None:
        super().__init__()
        self.paused = False
        self.show_help = True
        self.status = ""  # one-line readout drawn at the bottom
        self.held: set[int] = set()  # keys currently held down, for continuous controls
        self._help_text = arcade.Text(
            "", 10, HEIGHT - 20, arcade.color.LIGHT_GRAY, 11, width=WIDTH - 20,
            multiline=True,
        )  # fmt: skip
        self._status_text = arcade.Text("", 10, 10, arcade.color.WHITE, 12)

    # --- to override ----------------------------------------------------------
    def step(self, dt: float) -> None:
        """Advance the simulation by ``dt`` seconds."""

    def draw(self) -> None:
        """Draw the current state of the simulation."""

    # --- arcade callbacks -------------------------------------------------------
    def on_fixed_update(self, delta_time: float) -> None:
        if not self.paused:
            self.step(delta_time)

    def on_draw(self) -> None:
        self.clear()
        self.draw()
        if self.show_help:
            window = self.window
            demos = window.demos if isinstance(window, DemoWindow) else ()
            switch = (f"1-{len(demos)}: switch demo",) if len(demos) > 1 else ()
            lines = (self.title, *self.help, "P: pause  N: step  H: help", *switch)
            self._help_text.text = "\n".join(lines)
            self._help_text.draw()
        self._status_text.text = ("[PAUSED]  " if self.paused else "") + self.status
        self._status_text.draw()

    def on_key_release(self, symbol: int, modifiers: int) -> bool | None:
        self.held.discard(symbol)
        return None

    def on_key_press(self, symbol: int, modifiers: int) -> bool | None:
        self.held.add(symbol)
        match symbol:
            case arcade.key.P:
                self.paused = not self.paused
            case arcade.key.N if self.paused:
                self.step(self.window.fixed_delta_time)
            case arcade.key.H:
                self.show_help = not self.show_help
            case _ if (
                arcade.key.KEY_1 <= symbol <= arcade.key.KEY_9
                and isinstance(self.window, DemoWindow)
                and symbol - arcade.key.KEY_1 < len(self.window.demos) > 1
            ):
                self.window.show_demo(symbol - arcade.key.KEY_1)
            case _:
                return False
        return True


class DemoWindow(arcade.Window):
    def __init__(self, demos: Sequence[type[Demo]], title: str) -> None:
        super().__init__(WIDTH, HEIGHT, title, fixed_rate=FIXED_RATE)
        self.demos = demos
        arcade.set_background_color(arcade.color.BLACK)

    def show_demo(self, index: int) -> None:
        if 0 <= index < len(self.demos):
            demo = self.demos[index]()
            self.set_caption(demo.title)
            self.show_view(demo)


def run(*demos: type[Demo], title: str = "Programming Game AI by Example") -> None:
    window = DemoWindow(demos, title)
    window.show_demo(0)
    arcade.run()


# --- drawing helpers (taking Vector2D instead of separate x, y floats) ------------
def draw_line(start: Vector2D, end: Vector2D, color: Color, width: float = 1) -> None:
    arcade.draw_line(start.x, start.y, end.x, end.y, color, width)


def draw_arrow(start: Vector2D, end: Vector2D, color: Color, width: float = 2) -> None:
    draw_line(start, end, color, width)
    direction = end - start
    if not direction:
        return
    back = -direction.normalize() * 10
    for angle in (math.radians(25), -math.radians(25)):
        draw_line(end, end + back.rotate(angle), color, width)


def draw_circle(
    center: Vector2D, radius: float, color: Color, *, filled: bool = True, width: float = 1
) -> None:
    if filled:
        arcade.draw_circle_filled(center.x, center.y, radius, color)
    else:
        arcade.draw_circle_outline(center.x, center.y, radius, color, width)


def draw_polygon(points: Sequence[Vector2D], color: Color) -> None:
    arcade.draw_polygon_filled([(p.x, p.y) for p in points], color)


def draw_polyline(points: Sequence[Vector2D], color: Color, *, closed: bool = False) -> None:
    for a, b in itertools.pairwise(points):
        draw_line(a, b, color)
    if closed and len(points) > 2:
        draw_line(points[-1], points[0], color)


def _triangle_texture(size: int = 64) -> arcade.Texture:
    """A white dart pointing along +x, drawn once and tinted per sprite."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(image).polygon(
        [(0, size * 0.2), (size - 1, size / 2), (0, size * 0.8)], fill=(255, 255, 255, 255)
    )
    return arcade.Texture(image, hash="gameai-vehicle-triangle")


class VehicleSprites:
    """Many oriented triangles drawn in one batch: far faster than one polygon call each."""

    def __init__(self) -> None:
        self._texture = _triangle_texture()
        self._sprites: arcade.SpriteList[arcade.Sprite] = arcade.SpriteList()

    def draw(self, vehicles: Sequence[tuple[Vector2D, Vector2D, float, Color]]) -> None:
        """Draw ``(position, heading, radius, color)`` for each vehicle."""
        while len(self._sprites) < len(vehicles):
            self._sprites.append(arcade.Sprite(self._texture))
        while len(self._sprites) > len(vehicles):
            self._sprites.pop()
        for sprite, (position, heading, radius, color) in zip(self._sprites, vehicles, strict=True):
            sprite.position = (position.x, position.y)
            sprite.angle = -math.degrees(math.atan2(heading.y, heading.x))
            sprite.width = sprite.height = radius * 2
            sprite.color = color
        self._sprites.draw()
