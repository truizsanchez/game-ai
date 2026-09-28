"""Simple Soccer in a window. Run with ``python -m gameai.ch04_soccer``."""

from __future__ import annotations

import random

import arcade

from gameai.ch04_soccer.pitch import HEIGHT, WIDTH, SoccerPitch
from gameai.ch04_soccer.players import GoalKeeper, PlayerBase
from gameai.ch04_soccer.team import SoccerTeam
from gameai.ch04_soccer.team_states import TeamColor
from gameai.common.transformations import world_transform
from gameai.common.vector2d import Vector2D
from gameai.common.view import (
    HEIGHT as SCREEN_HEIGHT,
)
from gameai.common.view import (
    WIDTH as SCREEN_WIDTH,
)
from gameai.common.view import (
    Color,
    Demo,
    draw_circle,
    draw_line,
    draw_polygon,
    draw_polyline,
)

OFFSET = Vector2D((SCREEN_WIDTH - WIDTH) / 2, (SCREEN_HEIGHT - HEIGHT) / 2 - 30)
PLAYER_SHAPE = (Vector2D(-3, 8), Vector2D(3, 10), Vector2D(3, -10), Vector2D(-3, -8))
TEAM_COLORS: dict[TeamColor, Color] = {
    TeamColor.RED: arcade.color.RED,
    TeamColor.BLUE: arcade.color.DODGER_BLUE,
}
KEEPER_COLORS: dict[TeamColor, Color] = {
    TeamColor.RED: arcade.color.ORANGE,
    TeamColor.BLUE: arcade.color.CYAN,
}
GRASS = (20, 110, 40)


class SoccerDemo(Demo):
    title = "Simple Soccer"
    help = (
        "S: states  I: ids  G: regions  U: support spots  T: targets",
        "K: kick off again (new match)",
    )

    def __init__(self) -> None:
        super().__init__()
        self.seed = 1
        self.pitch = SoccerPitch(rng=random.Random(self.seed))
        self.show = {
            "states": True,
            "ids": False,
            "regions": False,
            "spots": True,
            "targets": False,
        }
        self.text = arcade.Text("", 0, 0, arcade.color.WHITE, 9)
        self.score_text = arcade.Text(
            "", SCREEN_WIDTH / 2, OFFSET.y + HEIGHT + 8, arcade.color.WHITE, 14,
            anchor_x="center", bold=True,
        )  # fmt: skip

    def step(self, dt: float) -> None:
        self.pitch.update()  # one tick per fixed update: the physics is per tick

    def on_key_press(self, symbol: int, modifiers: int) -> bool | None:
        toggles = {
            arcade.key.S: "states",
            arcade.key.I: "ids",
            arcade.key.G: "regions",
            arcade.key.U: "spots",
            arcade.key.T: "targets",
        }
        if symbol in toggles:
            self.show[toggles[symbol]] = not self.show[toggles[symbol]]
            return True
        if symbol == arcade.key.K:
            self.seed += 1
            self.pitch = SoccerPitch(rng=random.Random(self.seed))
            return True
        return super().on_key_press(symbol, modifiers)

    def label(self, text: str, at: Vector2D, color: Color = arcade.color.WHITE) -> None:
        self.text.text, self.text.color = text, color
        self.text.x, self.text.y = at.x, at.y
        self.text.draw()

    def draw(self) -> None:
        pitch = self.pitch
        area = pitch.playing_area
        arcade.draw_lbwh_rectangle_filled(
            OFFSET.x + area.left, OFFSET.y + area.bottom, area.width, area.height, GRASS
        )
        if self.show["regions"]:
            for region in pitch.regions:
                corners = [
                    Vector2D(region.left, region.bottom),
                    Vector2D(region.right, region.bottom),
                    Vector2D(region.right, region.top),
                    Vector2D(region.left, region.top),
                ]
                draw_polyline([OFFSET + c for c in corners], (60, 160, 80), closed=True)
                self.label(str(region.id), OFFSET + region.center, (120, 200, 140))
        middle_top = Vector2D(WIDTH / 2, area.top)
        middle_bottom = Vector2D(WIDTH / 2, area.bottom)
        draw_line(OFFSET + middle_top, OFFSET + middle_bottom, arcade.color.WHITE)
        draw_circle(OFFSET + area.center, area.height * 0.125, arcade.color.WHITE, filled=False)
        for wall in pitch.walls:
            draw_line(OFFSET + wall.start, OFFSET + wall.end, arcade.color.WHITE, 2)
        for goal, color in ((pitch.red_goal, TEAM_COLORS[TeamColor.RED]),
                            (pitch.blue_goal, TEAM_COLORS[TeamColor.BLUE])):  # fmt: skip
            draw_line(OFFSET + goal.post_a, OFFSET + goal.post_b, color, 4)

        for team in (pitch.red, pitch.blue):
            self.draw_team(team)
        draw_circle(OFFSET + pitch.ball.position, pitch.ball.bounding_radius, arcade.color.WHITE)

        red, blue = pitch.score
        self.score_text.text = f"Red {red} - {blue} Blue"
        self.score_text.draw()
        self.status = self.team_status(pitch.red) + "   |   " + self.team_status(pitch.blue)

    def draw_team(self, team: SoccerTeam) -> None:
        if self.show["spots"] and team.in_control:
            for spot in team.support_spots.spots:
                draw_circle(OFFSET + spot.position, spot.score, (200, 200, 200, 120), filled=False)
            if team.support_spots.best is not None:
                best = OFFSET + team.support_spots.best.position
                draw_circle(best, team.support_spots.best.score, arcade.color.YELLOW, filled=False)
        for player in team.players:
            self.draw_player(team, player)

    def draw_player(self, team: SoccerTeam, player: PlayerBase) -> None:
        is_keeper = isinstance(player, GoalKeeper)
        facing = player.heading
        if isinstance(player, GoalKeeper) and player.look_at:
            facing = player.look_at  # keepers always face the ball
        color = (KEEPER_COLORS if is_keeper else TEAM_COLORS)[team.color]
        shape = world_transform(PLAYER_SHAPE, player.position, facing, facing.perp())
        draw_polygon([OFFSET + p for p in shape], color)
        if player is team.controlling_player:
            draw_circle(OFFSET + player.position, 13, arcade.color.YELLOW, filled=False)
        if self.show["targets"]:
            draw_circle(OFFSET + player.steering.target, 3, color)
        info = []
        if self.show["ids"]:
            info.append(str(player.id))
        if self.show["states"]:
            info.append(player.state_name)
        if info:
            self.label(" ".join(info), OFFSET + player.position + Vector2D(-20, 12))

    @staticmethod
    def team_status(team: SoccerTeam) -> str:
        return f"{team.color.name.title()}: {team.fsm.current.name}"
