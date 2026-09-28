"""The pitch: owns the ball, goals, walls, teams and the per-tick loop (C++ ``SoccerPitch``)."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from gameai.ch04_soccer import team_states
from gameai.ch04_soccer.ball import SoccerBall
from gameai.ch04_soccer.params import Params, load
from gameai.ch04_soccer.pitch_geometry import Goal, Region
from gameai.ch04_soccer.players import PlayerBase
from gameai.ch04_soccer.team import SoccerTeam
from gameai.ch04_soccer.team_states import TeamColor
from gameai.common.geometry import Wall2D
from gameai.common.messaging import EntityRegistry, MessageDispatcher
from gameai.common.vector2d import Vector2D

WIDTH, HEIGHT = 700, 400  # the C++ window; the playing area has a 20 px border
BORDER = 20
REGIONS_X, REGIONS_Y = 6, 3


@dataclass(eq=False)
class SoccerPitch:
    params: Params = field(default_factory=load)
    rng: random.Random = field(default_factory=random.Random)
    tick: int = field(default=0, init=False)
    game_on: bool = field(default=True, init=False)
    goalkeeper_has_ball: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        p = self.params
        self.playing_area = Region(BORDER, BORDER, WIDTH - BORDER, HEIGHT - BORDER)
        self.regions = self._create_regions()
        mid_y, half_goal = HEIGHT / 2, p.goal_width / 2
        left, right = self.playing_area.left, self.playing_area.right
        self.red_goal = Goal(
            Vector2D(left, mid_y - half_goal), Vector2D(left, mid_y + half_goal), Vector2D(1, 0)
        )
        self.blue_goal = Goal(
            Vector2D(right, mid_y - half_goal), Vector2D(right, mid_y + half_goal), Vector2D(-1, 0)
        )
        self.walls = self._create_walls()
        self.ball = SoccerBall(
            Vector2D(WIDTH / 2, HEIGHT / 2), p.ball_size, mass=p.ball_mass, friction=p.friction
        )
        self.entities: EntityRegistry[PlayerBase] = EntityRegistry()
        self.dispatcher = MessageDispatcher(self.entities, self.clock)
        self.red = SoccerTeam(TeamColor.RED, self.red_goal, self.blue_goal, self)
        self.blue = SoccerTeam(TeamColor.BLUE, self.blue_goal, self.red_goal, self)
        self.red.opponents, self.blue.opponents = self.blue, self.red
        self.red.create_players()
        self.blue.create_players()

    def clock(self) -> float:
        """Seconds of game time, counted in ticks (the C++ code uses the wall clock)."""
        return self.tick / self.params.frame_rate

    def _create_regions(self) -> list[Region]:
        """A 6x3 grid numbered as in the C++ code: 17 is top-left, 0 is bottom-right.

        Columns run left to right and rows top to bottom, counting down from 17.
        """
        area = self.playing_area
        w, h = area.width / REGIONS_X, area.height / REGIONS_Y
        regions: list[Region | None] = [None] * (REGIONS_X * REGIONS_Y)
        index = len(regions) - 1
        for col in range(REGIONS_X):
            for row in range(REGIONS_Y):
                top = area.top - row * h
                regions[index] = Region(
                    area.left + col * w, top - h, area.left + (col + 1) * w, top, index
                )
                index -= 1
        return [r for r in regions if r is not None]

    def _create_walls(self) -> list[Wall2D]:
        """The boundary, anticlockwise (normals inwards), with gaps for the goal mouths."""
        a = self.playing_area
        bl, br = Vector2D(a.left, a.bottom), Vector2D(a.right, a.bottom)
        tr, tl = Vector2D(a.right, a.top), Vector2D(a.left, a.top)
        return [
            Wall2D(bl, br),
            Wall2D(br, self.blue_goal.post_a),
            Wall2D(self.blue_goal.post_b, tr),
            Wall2D(tr, tl),
            Wall2D(tl, self.red_goal.post_b),
            Wall2D(self.red_goal.post_a, bl),
        ]

    @property
    def all_players(self) -> list[PlayerBase]:
        return self.red.players + self.blue.players

    def update(self) -> None:
        """One tick: move the ball, let both teams think and act, check for goals."""
        self.tick += 1
        self.ball.update(self.walls)
        self.red.update()
        self.blue.update()
        old, new = self.ball.old_position, self.ball.position
        if self.blue_goal.scored(old, new) or self.red_goal.scored(old, new):
            self.game_on = False
            self.ball.place_at(Vector2D(WIDTH / 2, HEIGHT / 2))
            self.red.fsm.change_state(team_states.PREPARE_FOR_KICK_OFF)
            self.blue.fsm.change_state(team_states.PREPARE_FOR_KICK_OFF)

    @property
    def score(self) -> tuple[int, int]:
        """(red, blue) goals: a goal in the blue goal counts for red."""
        return self.blue_goal.goals_scored, self.red_goal.goals_scored
