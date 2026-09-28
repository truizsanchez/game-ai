import random
from collections.abc import Callable
from pathlib import Path

import pytest

from gameai.common.vector2d import Vector2D
from gameai.raven.bot import Brain, RavenBot
from gameai.raven.game import RavenGame

# A 200x200 room (y-down, as in real map files) with a 3x3 navigation grid, two spawn points,
# a health pack on node 2 and a shotgun on node 6. Walls list their inward normal.
ROOM = """9
Index: 0 PosX: 50 PosY: 50
Index: 1 PosX: 100 PosY: 50
Index: 2 PosX: 150 PosY: 50
Index: 3 PosX: 50 PosY: 100
Index: 4 PosX: 100 PosY: 100
Index: 5 PosX: 150 PosY: 100
Index: 6 PosX: 50 PosY: 150
Index: 7 PosX: 100 PosY: 150
Index: 8 PosX: 150 PosY: 150
{edges}
200 200
0 10 10 190 10 0 1
0 190 10 190 190 -1 0
0 190 190 10 190 0 -1
0 10 190 10 10 1 0
5 20 30 30 7 -1
5 21 170 170 7 -1
4 22 150 50 7 50 2
8 23 50 150 7 6
"""

# A corridor split by a sliding door at x=100, with a switch on the left side.
DOOR = """2
Index: 0 PosX: 50 PosY: 50
Index: 1 PosX: 150 PosY: 50
2
From: 0 To: 1 Cost: 100 Flags: 64 ID: 30
From: 1 To: 0 Cost: 100 Flags: 64 ID: 30
200 100
0 10 10 190 10 0 1
0 190 90 10 90 0 -1
11 30 100 10 100 90 1 31
12 31 30 6 60 50 5
5 40 30 50 7 -1
5 41 170 50 7 -1
"""


def grid_edges() -> str:
    lines = []
    for index in range(9):
        row, col = divmod(index, 3)
        for other in range(9):
            r, c = divmod(other, 3)
            if other != index and abs(r - row) <= 1 and abs(c - col) <= 1:
                cost = 50 * ((r - row) ** 2 + (c - col) ** 2) ** 0.5
                lines.append(f"From: {index} To: {other} Cost: {cost} Flags: 0 ID: -1")
    return f"{len(lines)}\n" + "\n".join(lines)


def write_map(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text)
    return path


@pytest.fixture
def room_path(tmp_path: Path) -> Path:
    return write_map(tmp_path, "room.map", ROOM.format(edges=grid_edges()))


@pytest.fixture
def door_path(tmp_path: Path) -> Path:
    return write_map(tmp_path, "door.map", DOOR)


@pytest.fixture
def make_game(room_path: Path) -> Callable[..., RavenGame]:
    def make(
        path: Path | None = None, bots: int = 2, brain: Callable[[RavenBot], Brain] | None = None
    ) -> RavenGame:
        game = RavenGame(path or room_path, rng=random.Random(4))
        if brain is not None:
            game.brain_factory = brain
            game.load_map(game.map_path)
        while len(game.bots) > bots:
            game.remove_bot()
        return game

    return make


def place(bot: RavenBot, x: float, y: float, facing: Vector2D = Vector2D(1, 0)) -> RavenBot:  # noqa: B008
    """Spawn a bot at a position (y up), facing a direction."""
    bot.spawn(Vector2D(x, y))
    bot.facing = bot.heading = facing
    return bot
