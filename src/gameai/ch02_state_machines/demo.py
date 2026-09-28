"""West World in a window: where everyone is, what state they are in, what they say and
which telegrams are on their way. Run with ``python -m gameai.ch02_state_machines``.
"""

from __future__ import annotations

from collections import deque

import arcade

from gameai.ch02_state_machines.westworld import create_world
from gameai.ch02_state_machines.westworld.miner import Miner
from gameai.ch02_state_machines.westworld.wife import MinersWife
from gameai.ch02_state_machines.westworld.world import TICK
from gameai.ch02_state_machines.westworld_common import EntityId, Location, Tone
from gameai.common.vector2d import Vector2D
from gameai.common.view import WIDTH, Demo, draw_circle

PLACES = {
    Location.SHACK: Vector2D(130, 430),
    Location.GOLDMINE: Vector2D(330, 430),
    Location.BANK: Vector2D(530, 430),
    Location.SALOON: Vector2D(730, 430),
}
BOX_W, BOX_H = 170, 90
TONE_COLORS = {
    Tone.MINER: arcade.color.SALMON,
    Tone.WIFE: arcade.color.LIGHT_GREEN,
    Tone.EVENT: arcade.color.YELLOW,
}
LOG_LINES = 14


class WestWorldDemo(Demo):
    title = "West World: Miner Bob and Elsa"
    help = ("+/-: faster / slower", "N while paused: one tick")

    def __init__(self) -> None:
        super().__init__()
        self.log: deque[tuple[str, Tone]] = deque(maxlen=LOG_LINES)
        self.world = create_world(lambda line, tone: self.log.append((line, tone)))
        bob = self.world.entities.get(EntityId.MINER_BOB)
        elsa = self.world.entities.get(EntityId.ELSA)
        assert isinstance(bob, Miner) and isinstance(elsa, MinersWife)
        self.bob, self.elsa = bob, elsa
        self.interval = TICK
        self.elapsed = 0.0
        self.labels = [
            arcade.Text(loc.name.title(), p.x, p.y + BOX_H / 2 - 18, arcade.color.WHITE, 12,
                        anchor_x="center", bold=True)
            for loc, p in PLACES.items()
        ]  # fmt: skip
        self.text = arcade.Text("", 0, 0, arcade.color.WHITE, 11)

    def step(self, dt: float) -> None:
        self.elapsed += dt
        if self.elapsed >= self.interval:
            self.elapsed = 0.0
            self.world.update()

    def on_key_press(self, symbol: int, modifiers: int) -> bool | None:
        match symbol:
            case arcade.key.N if self.paused:
                self.world.update()
            case arcade.key.PLUS | arcade.key.EQUAL | arcade.key.NUM_ADD:
                self.interval = max(0.05, self.interval / 1.5)
            case arcade.key.MINUS | arcade.key.NUM_SUBTRACT:
                self.interval = min(5.0, self.interval * 1.5)
            case _:
                return super().on_key_press(symbol, modifiers)
        return True

    def write(self, text: str, x: float, y: float, color: arcade.types.Color) -> None:
        self.text.text, self.text.x, self.text.y, self.text.color = text, x, y, color
        self.text.draw()

    def draw(self) -> None:
        for place in PLACES.values():
            arcade.draw_lbwh_rectangle_outline(
                place.x - BOX_W / 2, place.y - BOX_H / 2, BOX_W, BOX_H, arcade.color.GRAY, 2
            )
        for label in self.labels:
            label.draw()

        bob, elsa = self.bob, self.elsa
        bob_at = PLACES[bob.location] + Vector2D(-25 if bob.location is Location.SHACK else 0, -10)
        elsa_at = PLACES[elsa.location] + Vector2D(25, -10)
        draw_circle(bob_at, 12, TONE_COLORS[Tone.MINER])
        draw_circle(elsa_at, 12, TONE_COLORS[Tone.WIFE])

        self.write(f"Miner Bob: {bob.fsm.current.name}", 20, 350, TONE_COLORS[Tone.MINER])
        self.write(
            f"gold {bob.gold_carried}  bank {bob.money_in_bank}  thirst {bob.thirst}  "
            f"fatigue {bob.fatigue}",
            20, 330, arcade.color.LIGHT_GRAY,
        )  # fmt: skip
        global_state = elsa.fsm.global_state.name if elsa.fsm.global_state else "-"
        self.write(
            f"Elsa: {elsa.fsm.current.name}  (global: {global_state})",
            WIDTH / 2, 350, TONE_COLORS[Tone.WIFE],
        )  # fmt: skip
        now = self.world.clock()
        pending = ", ".join(
            f"{t.msg.name} to {EntityId(t.receiver).display_name} in {t.dispatch_time - now:.1f}s"
            for t in self.world.dispatcher.pending
        )
        self.write(f"Telegrams in flight: {pending or 'none'}", WIDTH / 2, 330, arcade.color.YELLOW)

        for i, (line, tone) in enumerate(self.log):
            self.write(line, 20, 295 - i * 19, TONE_COLORS[tone])
        self.status = f"time {now:.1f}s  |  one tick every {self.interval:.2f}s"
