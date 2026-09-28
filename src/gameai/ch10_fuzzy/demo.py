"""Fuzzy inference visualized. Run with ``python -m gameai.ch10_fuzzy``.

The rocket launcher module of the chapter: move the distance and ammo inputs and watch the
membership of each set, the clipped output sets and the crisp desirability.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable

import arcade

from gameai.ch10_fuzzy import rocket_launcher_combs
from gameai.common.fuzzy import DefuzzifyMethod, FuzzySet, FuzzyVariable
from gameai.common.vector2d import Vector2D
from gameai.common.view import Color, Demo, draw_line
from gameai.raven.weapon_fuzzy import AMMO, DESIRABILITY, DISTANCE, desirability, rocket_launcher

PANEL_W, PANEL_H = 260.0, 110.0
type ToScreen = Callable[[float, float], Vector2D]

COLORS: tuple[Color, ...] = (arcade.color.RED, arcade.color.YELLOW, arcade.color.GREEN)


class FuzzyDemo(Demo):
    title = "Fuzzy weapon desirability (rocket launcher)"
    help = ("Left/Right: distance  Down/Up: ammo", "C: Combs method rules on/off")

    def __init__(self) -> None:
        super().__init__()
        self.distance, self.ammo = 200.0, 8.0
        self.combs = False
        self.text = arcade.Text("", 0, 0, arcade.color.WHITE, 10)

    def step(self, dt: float) -> None:
        held = self.held
        self.distance += 150 * dt * ((arcade.key.RIGHT in held) - (arcade.key.LEFT in held))
        self.ammo += 15 * dt * ((arcade.key.UP in held) - (arcade.key.DOWN in held))
        self.distance = max(0.0, min(self.distance, 500.0))
        self.ammo = max(0.0, min(self.ammo, 100.0))

    def on_key_press(self, symbol: int, modifiers: int) -> bool | None:
        if symbol == arcade.key.C:
            self.combs = not self.combs
            return True
        return super().on_key_press(symbol, modifiers)

    def label(self, text: str, x: float, y: float, color: Color = arcade.color.WHITE) -> None:
        self.text.text, self.text.x, self.text.y, self.text.color = text, x, y, color
        self.text.draw()

    def draw(self) -> None:
        fm = rocket_launcher_combs() if self.combs else rocket_launcher()
        crisp = desirability(fm, self.distance, round(self.ammo))
        centroid = fm.defuzzify(DESIRABILITY, DefuzzifyMethod.CENTROID)
        self.draw_variable(fm.variables[DISTANCE], "Distance to target", 40, 330, self.distance,
                           max_x=500)  # fmt: skip
        self.draw_variable(fm.variables[AMMO], "Ammo status", 420, 330, self.ammo)
        self.draw_variable(fm.variables[DESIRABILITY], "Desirability (clipped by the rules)",
                           40, 130, crisp, output=True)  # fmt: skip
        rules = "Combs (6 rules)" if self.combs else "traditional (9 rules)"
        self.label(f"Rules: {rules}", 420, 170)
        self.label(f"MaxAv: {crisp:.2f}", 420, 145, arcade.color.YELLOW)
        self.label(f"Centroid: {centroid:.2f}", 420, 125, arcade.color.ORANGE)
        self.status = f"distance {self.distance:.0f}   ammo {round(self.ammo)}"

    def draw_variable(self, variable: FuzzyVariable, title: str, x0: float, y0: float,
                      value: float, *, max_x: float | None = None,
                      output: bool = False) -> None:  # fmt: skip
        """Plot a variable's sets; mark the input value, or clip the sets for the output."""
        lo, hi = variable.min_range, max_x if max_x is not None else variable.max_range

        def to_screen(x: float, dom: float) -> Vector2D:
            return Vector2D(x0 + (x - lo) / (hi - lo) * PANEL_W, y0 + dom * PANEL_H)

        self.label(title, x0, y0 + PANEL_H + 12)
        draw_line(to_screen(lo, 0), to_screen(hi, 0), arcade.color.GRAY)
        for (name, fuzzy_set), color in zip(variable.sets.items(), COLORS, strict=False):
            self.draw_set(fuzzy_set, to_screen, lo, hi, color, clip=output)
            self.label(f"{name}: {fuzzy_set.dom:.2f}", x0 + PANEL_W + 10,
                       y0 + PANEL_H - 15 * list(variable.sets).index(name), color)  # fmt: skip
        draw_line(to_screen(value, 0), to_screen(value, 1.05), arcade.color.WHITE, 2)

    @staticmethod
    def draw_set(fuzzy_set: FuzzySet, to_screen: ToScreen, lo: float, hi: float,
                 color: Color, *, clip: bool) -> None:  # fmt: skip
        """Draw a set's membership curve; for outputs, fill it clipped at its DOM."""
        corners = sorted({max(lo, min(hi, x)) for x in (fuzzy_set.left, fuzzy_set.peak,
                                                         fuzzy_set.right, lo, hi)})  # fmt: skip
        xs = [a + (b - a) * i / 60 for a, b in itertools.pairwise(corners) for i in range(61)]
        curve = [(x, fuzzy_set.membership(x)) for x in xs]
        outline = [to_screen(x, dom) for x, dom in curve]
        for a, b in itertools.pairwise(outline):
            draw_line(a, b, color, 2)
        if clip and fuzzy_set.dom > 0:  # fill the clipped set with thin vertical strips
            fill = (color[0], color[1], color[2], 110)
            for x, dom in curve:
                if (height := min(dom, fuzzy_set.dom)) > 0:
                    draw_line(to_screen(x, 0), to_screen(x, height), fill, 3)
