"""Raven in a window. Run with ``python -m gameai.raven``.

Right-click a bot to select it, right-click it again to possess it. A possessed bot faces
the mouse, moves where you right-click (hold Q to queue positions), fires at left clicks and
switches weapon with 1-4. X releases it.
"""

from __future__ import annotations

import random
from typing import ClassVar

import arcade

from gameai.common.transformations import world_transform
from gameai.common.vector2d import Vector2D
from gameai.common.view import HEIGHT, WIDTH, Color, Demo, draw_circle, draw_line, draw_polygon
from gameai.raven.bot import SHAPE, RavenBot
from gameai.raven.entity_types import EntityType
from gameai.raven.game import RavenGame, original_map
from gameai.raven.items import HealthGiver, WeaponGiver
from gameai.raven.projectiles import Bolt, Pellet, Projectile, Rocket, Slug

MAPS = ("Raven_DM1.map", "Raven_DM1_With_Doors.map")
SCALE = 1.15
OFFSET = Vector2D(WIDTH - 500 * SCALE - 10, (HEIGHT - 470 * SCALE) / 2 - 10)
ITEM_COLORS: dict[EntityType, Color] = {
    EntityType.HEALTH: arcade.color.RED,
    EntityType.SHOTGUN: arcade.color.ORANGE,
    EntityType.RAIL_GUN: arcade.color.CYAN,
    EntityType.ROCKET_LAUNCHER: arcade.color.YELLOW,
}


def screen(p: Vector2D) -> Vector2D:
    return OFFSET + p * SCALE


def world(x: float, y: float) -> Vector2D:
    return (Vector2D(x, y) - OFFSET) / SCALE


class RavenDemo(Demo):
    title = "Raven"
    help = (
        "Right click: select / possess / move",
        "Left click: fire  1-4: weapon",
        "Q+right click: queue  X: release",
        "Up/Down: add/remove bot",
        "G: graph  L: labels  M: map",
    )
    WEAPON_KEYS: ClassVar[dict[int, EntityType]] = {
        arcade.key.KEY_1: EntityType.BLASTER,
        arcade.key.KEY_2: EntityType.SHOTGUN,
        arcade.key.KEY_3: EntityType.ROCKET_LAUNCHER,
        arcade.key.KEY_4: EntityType.RAIL_GUN,
    }

    def __init__(self) -> None:
        super().__init__()
        self.map_index = 0
        self.show_graph = False
        self.show_labels = True
        self.text = arcade.Text("", 0, 0, arcade.color.WHITE, 9)
        self.game = self._new_game()

    def _new_game(self) -> RavenGame:
        path = original_map(MAPS[self.map_index])
        if path is None:
            raise SystemExit("Raven maps not found: set GAMEAI_ORIGINAL_SOURCE")
        return RavenGame(path, rng=random.Random())

    # --- input ---------------------------------------------------------------------------------
    def step(self, dt: float) -> None:
        self.game.update()

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int) -> None:
        self.game.cursor = world(x, y)

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> None:
        position = world(x, y)
        if button == arcade.MOUSE_BUTTON_RIGHT:
            self.game.click_right(position, queue=arcade.key.Q in self.held)
        elif button == arcade.MOUSE_BUTTON_LEFT:
            self.game.click_left(position)

    def on_key_press(self, symbol: int, modifiers: int) -> bool | None:
        game = self.game
        if symbol in self.WEAPON_KEYS:
            game.change_weapon_of_possessed_bot(self.WEAPON_KEYS[symbol])
        elif symbol == arcade.key.X:
            game.exorcise()
        elif symbol == arcade.key.UP:
            game.add_bots(1)
        elif symbol == arcade.key.DOWN:
            game.remove_bot()
        elif symbol == arcade.key.G:
            self.show_graph = not self.show_graph
        elif symbol == arcade.key.L:
            self.show_labels = not self.show_labels
        elif symbol == arcade.key.M:
            self.map_index = (self.map_index + 1) % len(MAPS)
            self.game = self._new_game()
        else:
            return super().on_key_press(symbol, modifiers)
        return True

    # --- drawing -------------------------------------------------------------------------------
    def label(self, text: str, at: Vector2D, color: Color = arcade.color.WHITE) -> None:
        self.text.text, self.text.color, self.text.x, self.text.y = text, color, at.x, at.y
        self.text.draw()

    def line(self, a: Vector2D, b: Vector2D, color: Color, width: float = 1) -> None:
        draw_line(screen(a), screen(b), color, width)

    def draw(self) -> None:
        game = self.game
        if self.show_graph:
            for edge in game.map.graph.all_edges():
                a, b = game.map.graph.node(edge.from_index), game.map.graph.node(edge.to_index)
                self.line(a.position, b.position, (60, 60, 60))
        for wall in game.map.walls:
            self.line(wall.start, wall.end, arcade.color.LIGHT_GRAY, 2)
        for door in game.map.doors:
            for index in door.wall_indices:
                wall = game.map.walls[index]
                self.line(wall.start, wall.end, arcade.color.BROWN, 3)
        for spawn in game.map.spawn_points:
            draw_circle(screen(spawn), 4, (90, 90, 90), filled=False)
        self.draw_items()
        for grave in game.graves.graves:
            self.label("RIP", screen(grave.position) - Vector2D(8, 4), arcade.color.GRAY)
        for projectile in game.projectiles:
            self.draw_projectile(projectile)
        for bot in game.bots:
            if bot.is_alive:
                self.draw_bot(bot)
        self.draw_selection()
        self.status = self.status_line()

    def draw_items(self) -> None:
        for item in self.game.map.items():
            if not item.active:
                continue
            color = ITEM_COLORS[item.entity_type]
            center = screen(item.position)
            if isinstance(item, HealthGiver):
                draw_line(center - Vector2D(5, 0), center + Vector2D(5, 0), color, 3)
                draw_line(center - Vector2D(0, 5), center + Vector2D(0, 5), color, 3)
            elif isinstance(item, WeaponGiver):
                draw_circle(center, 5, color, filled=False, width=2)

    def draw_projectile(self, projectile: Projectile) -> None:
        match projectile:
            case Bolt():
                tail = projectile.position - projectile.heading * 5
                self.line(tail, projectile.position, arcade.color.GREEN, 2)
            case Rocket() if projectile.impacted:
                draw_circle(
                    screen(projectile.position),
                    projectile.current_blast_radius * SCALE,
                    arcade.color.ORANGE_RED,
                    filled=False,
                    width=2,
                )
            case Rocket():
                draw_circle(screen(projectile.position), 3, arcade.color.ORANGE_RED)
            case Slug():
                self.line(projectile.origin, projectile.impact_point, arcade.color.CYAN, 2)
            case Pellet():
                draw_circle(screen(projectile.impact_point), 2, arcade.color.YELLOW)

    def draw_bot(self, bot: RavenBot) -> None:
        scale = self.game.params.bot.scale
        outline = world_transform(SHAPE, bot.position, bot.facing, bot.facing.perp(),
                                  Vector2D(scale, scale))  # fmt: skip
        draw_polygon([screen(p) for p in outline], arcade.color.BLUE_GRAY)
        draw_circle(screen(bot.position), 6 * scale * SCALE, arcade.color.BROWN)
        self.line(bot.position, bot.position + bot.facing * 10, arcade.color.WHITE, 2)
        if bot.hit_ticks_left > 0:
            draw_circle(screen(bot.position), (bot.bounding_radius + 2) * SCALE,
                        arcade.color.RED, filled=False, width=3)  # fmt: skip
        if self.show_labels:
            text = f"{bot.id} H:{bot.health} S:{bot.score}"
            self.label(text, screen(bot.position) + Vector2D(-22, 12), arcade.color.LIGHT_GREEN)

    def draw_selection(self) -> None:
        bot = self.game.selected_bot
        if bot is None or not bot.is_alive:
            return
        color = arcade.color.SKY_BLUE if bot.possessed else arcade.color.RED
        draw_circle(screen(bot.position), (bot.bounding_radius + 3) * SCALE, color, filled=False)
        for opponent in bot.memory.recently_sensed_opponents():
            if opponent.is_alive:
                r = opponent.bounding_radius * SCALE
                c = screen(opponent.position)
                arcade.draw_lbwh_rectangle_outline(c.x - r, c.y - r, 2 * r, 2 * r,
                                                   arcade.color.ORANGE)  # fmt: skip
        if bot.target_bot is not None and bot.target_bot.is_alive:
            c = screen(bot.target_bot.position)
            r = bot.target_bot.bounding_radius * SCALE + 3
            arcade.draw_lbwh_rectangle_outline(c.x - r, c.y - r, 2 * r, 2 * r, arcade.color.RED, 2)

    def status_line(self) -> str:
        game, bot = self.game, self.game.selected_bot
        base = f"{game.map_path.name}  t={game.clock():.0f}s  bots {len(game.bots)}"
        if bot is None:
            return base + "  |  right-click a bot to select it"
        weapon = bot.weapons.current
        ammo = "inf" if weapon.unlimited_ammo else str(weapon.rounds_left)
        target = f"#{bot.target_bot.id}" if bot.target_bot else "none"
        mode = "POSSESSED" if bot.possessed else "selected"
        return (
            f"{base}  |  bot {bot.id} {mode}: health {bot.health}, "
            f"{weapon.type.label} ({ammo}), target {target}"
        )
